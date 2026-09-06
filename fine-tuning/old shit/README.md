# Arabic Legal Qwen2.5-7B — Fine-tuning Pipeline

Domain adaptation of `Qwen/Qwen2.5-7B-Instruct` on 3 scanned Arabic legal
PDFs, via QLoRA on an RTX 5060. Fine-tuning only — no RAG, no vector DB.

## 1. Recommended architecture

```
3 scanned PDFs
   │  PyMuPDF render @300dpi
   ▼
PaddleOCR (PP-StructureV3, Arabic)         -> data/ocr/*.jsonl (per-page)
   │
   ▼
Clean + normalize + QC + dedup + article/chapter extraction
   │                                        -> data/processed/{corpus,articles}.jsonl
   ▼
Rule-based grounded SFT example generation  -> data/sft/{train,val}.jsonl
   │
   ▼
Single-stage QLoRA SFT (Qwen2.5-7B-Instruct, 4-bit NF4, assistant-only loss)
   │                                        -> models/sft/ (LoRA adapter)
   ▼
Inference (adapter or merged)
```

**No separate CPT stage.** See "Why this architecture" below.

## 2. Why this architecture (deviations from the naive CPT→SFT plan)

- **CPT dropped.** Continued pretraining is raw next-token prediction over
  the OCR'd book text. With only 3 books (a few hundred thousand tokens at
  most), a CPT stage either does almost nothing (too few steps to shift the
  model) or memorizes the exact source text (too many steps on too little
  data) — and it does this *before* SFT, meaning you also risk degrading
  Qwen's instruction-following ability with no guarantee SFT fully restores
  it afterward. There's no dataset-size regime here where CPT is the right
  call.
- **Knowledge injection happens inside SFT instead**, via templated
  recitation/continuation examples generated straight from the cleaned
  corpus (`build_recitation_examples` in `build_sft_dataset.py`). This gives
  the model the same raw-text exposure CPT would, but under the chat format
  and completion-only loss the whole time, and lets one LoRA adapter,
  trained once, do the whole job — which also resolves the "CPT adapter →
  SFT adapter" transition question from the brief: there's only one adapter.
- **Synthetic SFT data is template-based, not LLM-generated.** An LLM asked
  to invent Q&A pairs from legal text can paraphrase inaccurately or
  fabricate a conclusion not actually stated — unacceptable for a legal
  assistant. Every example's answer is either the verbatim article text or a
  verbatim extracted span (a definition, a cross-reference list). Nothing is
  invented or paraphrased.
- **Full fine-tuning is not realistic** on an 8GB RTX 5060 for a 7B model —
  QLoRA is required, not optional.

## 3. OCR strategy

**PaddleOCR (PP-StructureV3) chosen over Tesseract, EasyOCR, and Surya:**
- Arabic recognition quality is meaningfully better than Tesseract on
  scanned book-quality fonts and justified text, which is what legal
  book PDFs typically are.
- PP-StructureV3's layout analysis reads multi-column pages and tables in
  correct reading order — plain top-to-bottom bounding-box sorting (what
  Tesseract/EasyOCR effectively give you) interleaves columns incorrectly.
- Runs fully offline, Apache-2.0 licensed, works on GPU or CPU, and the GPU
  requirement for OCR is trivial compared to training (OCR runs once, not
  in a training loop).
- Surya has decent multilingual OCR but its Arabic support is newer and
  less battle-tested than PaddleOCR's dedicated Arabic recognition model;
  not worth the added dependency for a one-time OCR pass.

DPI is set to 300 (`config.OCR_CFG.render_dpi`) — enough for accurate
recognition on book-scan quality without exploding memory/processing time.
OCR confidence is recorded per page and threaded through to the quality
filter (script 2), not decided at OCR time.

## 4. Dataset strategy

- **Conservative normalization only**: tatweel removal and whitespace
  cleanup. Alef-variant unification (إ/أ/آ→ا) and diacritic stripping are
  deliberately **not** applied — they change the literal source text, and
  legal citations/terminology must stay exact.
- **Headers/footers/page numbers removed** via a per-document repetition
  heuristic (a short line recurring on ~40%+ of pages is boilerplate), never
  touching lines that match an article heading.
- **Legal article numbers ("المادة"/"مادة") are the structural anchor** —
  articles are extracted as self-contained chunks with `chapter` metadata
  where recoverable, because a legal article is naturally a whole,
  semantically complete training unit; arbitrary token-length chunking
  would frequently cut an article (and its meaning) in half.
- **Quality filtering**: per-page score from Arabic-character ratio,
  punctuation ratio, and repeated-character runs (see
  `data/processed/ocr_quality_report.csv` after running the pipeline).
  Pages below threshold are excluded from training, not silently kept.
- **Deduplication**: exact + near-duplicate (`difflib` ratio ≥0.92) page
  detection, common with repeated cover/appendix pages in scanned books.
- **Very short fragments discarded** (`min_fragment_chars`), so isolated
  page-number noise never becomes a "training example."

## 5. CPT strategy

Not used. See section 2.

## 6. SFT strategy

Per article: (1) direct recall Q&A, (2) cloze-style continuation, (3)
definition-extraction Q&A when the article contains a "يقصد بـ" definition
clause. Per chapter (train split only): a "which articles cover X" lookup.
Plus recitation/continuation examples from general corpus pages. All
answers are verbatim spans from the source — zero hallucination risk by
construction.

- **Split before generation**: articles are divided into train/val *before*
  any examples are generated from them, so validation never contains a
  near-duplicate of a training example (no leakage).
- **Loss**: assistant-only (completion-only), via
  `DataCollatorForCompletionOnlyLM` matched to Qwen2.5's
  `<|im_start|>assistant\n` turn marker — loss over user/system tokens would
  train the model to predict questions, not answers.
- **Epochs**: 3 by default (`config.TRAIN_CFG.num_train_epochs`), watched
  against `eval_loss` with `load_best_model_at_end=True` — with a dataset
  this size, more than a handful of epochs risks memorizing the exact
  phrasing of the generated questions rather than generalizing.

## 7. RTX 5060 optimization

Assume the non-Ti RTX 5060 (8GB VRAM) unless you have the 16GB Ti, in which
case you can raise `max_seq_length` and drop `gradient_accumulation_steps`.

| Setting | Value | Why |
|---|---|---|
| Quantization | 4-bit NF4 + double quant | 7B model must fit in 8GB alongside activations/optimizer state |
| Compute dtype | bf16 | RTX 50-series (Blackwell) supports bf16 natively |
| LoRA target modules | q/k/v/o + gate/up/down proj | attention-only under-adapts for domain vocabulary/style |
| LoRA rank / alpha | 16 / 32 | balances adaptation capacity vs. overfitting on ~3 books |
| Sequence length | 1536 | fits comfortably in 8GB with the above; raise cautiously if you have 16GB |
| Batch size / grad accum | 1 / 16 | effective batch 16 without exceeding VRAM |
| Optimizer | `paged_adamw_8bit` | standard QLoRA memory-saving optimizer |
| Attention impl | SDPA | Flash-Attention 2 Blackwell wheels are not reliably available yet; SDPA is safe and fast enough |

**OCR should run on GPU when convenient but is not VRAM-sensitive** (it's a
single forward pass per page, not a training loop) — run it separately from
training regardless, since PaddleOCR and the training stack use different
frameworks/CUDA contexts and there's no benefit to interleaving them.

**Approximate VRAM usage during training**: ~5.5–7GB (4-bit 7B weights
~4.5GB + LoRA adapter + activations at seq_len 1536 + paged optimizer
state). Expect to be close to the 8GB ceiling — reduce `max_seq_length`
first if you OOM, then `gradient_accumulation_steps` is safe to change
without hurting memory.

**Expected training time**: a few hundred to ~1,500 training examples (3
books, article-based) at 3 epochs, effective batch 16, is on the order of
a few hundred to ~1,500 optimizer steps — realistically **1–4 hours** on an
RTX 5060, depending on exact example count and sequence lengths. This is
not an A100-scale job.

## 8. Project structure

```
legal-llm/
├── config.py
├── requirements.txt
├── README.md
├── data/
│   ├── pdfs/          # <- put your 3 scanned PDFs here
│   ├── ocr/            # per-page OCR jsonl (generated)
│   ├── processed/       # cleaned corpus + articles + QC report (generated)
│   └── sft/             # train.jsonl / val.jsonl (generated)
├── models/
│   ├── sft/              # LoRA adapter output
│   └── merged/            # optional merged model (inference --mode merged)
├── logs/
└── scripts/
    ├── ocr.py
    ├── clean_dataset.py
    ├── build_sft_dataset.py
    ├── validate_dataset.py
    ├── train_sft.py
    └── inference.py
```

## 9. requirements.txt

See `requirements.txt`. Install `torch` separately first from the CUDA 12.8
index (see Installation below) — this is the one dependency you must not
take from the default PyPI index given the RTX 5060/Blackwell requirement.

## 10. Complete code

All in `scripts/` and `config.py`, described above.

## 11. Installation

```bash
python3.11 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# Torch FIRST, from the cu128 index (Blackwell/sm_120 needs PyTorch >=2.7.0):
pip install torch --index-url https://download.pytorch.org/whl/cu128

pip install -r requirements.txt
```

Verify the GPU is actually visible before doing anything else:
```bash
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

## 12. Usage

```bash
# 1. Place your 3 scanned PDFs
cp /path/to/*.pdf data/pdfs/

# 2. OCR
python scripts/ocr.py

# 3. Clean, normalize, extract structure
python scripts/clean_dataset.py

# 4. Build the SFT dataset
python scripts/build_sft_dataset.py

# 5. Validate everything before spending GPU time
python scripts/validate_dataset.py

# 6. Train (QLoRA SFT)
python scripts/train_sft.py

# 7. Chat with it
python scripts/inference.py --mode adapter
# or, for a standalone merged model:
python scripts/inference.py --mode merged --merge
```

## 13. Expected hardware usage

- **OCR**: a few minutes per ~100-page book on GPU; CPU is fine too, just
  slower (roughly 3–5x).
- **Training**: ~5.5–7GB VRAM, 1–4 hours total depending on corpus size
  (see section 7). System RAM: 16GB recommended (4-bit loading + dataset
  processing).
- **Merging** (optional, `--mode merged`): done in bf16 on CPU in this
  script to avoid needing >8GB VRAM for the merge step; needs ~16GB free
  RAM and ~16GB disk for the merged model.

## 14. Final engineering verification

Checked before delivering this: Qwen2.5 chat-template turn markers match
the `DataCollatorForCompletionOnlyLM` response template used; PEFT/TRL/
Transformers/BitsAndBytes/Accelerate versions pinned to a mutually
compatible combination (TRL 0.12.x's `SFTConfig`/`SFTTrainer` API matches
what `train_sft.py` calls); `use_cache=False` is set alongside gradient
checkpointing (a common source of silent training bugs when omitted);
tokenizer `pad_token` is set explicitly (Qwen2.5 has no default pad token);
`remove_unused_columns=False` is set so the collator still sees the raw
`text` field; article/train-val split happens before example generation to
prevent leakage; the validation script checks for empty datasets, malformed
examples, and exercises the actual chat template before training starts.

**Genuine limitations that remain**: (1) the `ARTICLE_HEADING` regex
assumes "المادة"/"مادة" numbering — if your specific books use a different
convention (e.g., spelled-out numbers, or "الفقرة" instead), you'll need to
adjust the regex after inspecting `data/ocr/*.jsonl` once, per the warning
`clean_dataset.py` prints if very few articles are found; (2) OCR quality
on heavily degraded scans (skewed pages, low contrast) may still need a
manual DPI/deskew adjustment — the QC report tells you which pages, but
doesn't fix them; (3) exact per-run VRAM headroom on an 8GB card is tight,
so `max_seq_length`/`gradient_accumulation_steps` are the first two knobs
to touch if you hit an OOM, and are deliberately centralized in
`config.py` for that reason.
