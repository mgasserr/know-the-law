# Fine-tuning: Qwen2.5-7B-Instruct (QLoRA) on Egyptian Law

Domain-adapts Qwen2.5-7B-Instruct on your 3 legal PDFs using QLoRA,
tuned to fit an 8GB GPU.

## Folder layout

```
know-the-law/
├── data/                          <- your existing 3 PDFs (shared with rag/)
├── rag/                           <- your existing FastAPI backend
└── fine-tuning/
    ├── requirements.txt
    ├── data_prep.py                <- builds the training set from the PDFs
    ├── train_qlora.py              <- QLoRA training
    ├── inference_test.py           <- sanity-check the trained adapter
    ├── merge_lora.py               <- optional: bake adapter into a standalone model
    └── qwen-legal-qlora/           <- created after training (the adapter)
```

## Setup

```bash
cd fine-tuning
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
```

## Run, in order

```bash
python data_prep.py       # extracts + chunks the 3 PDFs -> data/finetune_dataset.jsonl
python train_qlora.py     # trains the LoRA adapter -> qwen-legal-qlora/
python inference_test.py  # loads base model + adapter, asks 2 test questions
```

`data_prep.py` and `inference_test.py` are cheap on VRAM (tokenizer only /
generation only). `train_qlora.py` is the one that needs your GPU.

## Why this fits in 8GB

- Base model loaded in **4-bit NF4** (bitsandbytes) — ~4.5-5GB for weights.
- Only LoRA adapter weights (a few million params) are trained — the base
  model stays frozen, so there's no full-model optimizer state to store.
- **Gradient checkpointing** trades some training speed for a large cut in
  activation memory.
- **`paged_adamw_8bit`** optimizer avoids VRAM spikes during the optimizer step.
- Batch size of 1 with gradient accumulation (effective batch = 16) instead
  of a large per-step batch.
- `max_seq_length=768` bounds how much activation memory each step needs.

## If you still hit `CUDA out of memory`

Try these, in order of impact:

1. **Check for a leaked process first** — run `nvidia-smi` before starting
   training. If VRAM is already partially used by a leftover Python
   process from a previous run (this happened with your RAG server
   earlier), kill it: `taskkill /F /PID <pid>`.
2. Lower `MAX_SEQ_LENGTH` in `train_qlora.py` from 768 to 512.
3. Increase `GRAD_ACCUMULATION_STEPS` (e.g. 16 -> 32) — same effective
   batch size, lower peak memory.
4. Lower `LORA_R` from 16 to 8.
5. Close anything else touching the GPU (browser hardware acceleration,
   other Python processes, etc.) — your card only has 8GB total and
   Windows itself reserves some of it for display.

## After training

The adapter in `qwen-legal-qlora/` is small (tens of MB) and is **not** a
full model — it's meant to be loaded on top of the 4-bit base model, exactly
like `inference_test.py` does. You generally don't need `merge_lora.py`
unless you specifically want a standalone merged checkpoint (e.g. to convert
to GGUF for llama.cpp/Ollama later).

To wire the fine-tuned adapter into your existing RAG backend, swap the
`AutoModelForCausalLM.from_pretrained(...)` call in `RAG.py`'s
`load_llm_pipeline()` for the same base-model-plus-adapter loading pattern
used in `inference_test.py`.
