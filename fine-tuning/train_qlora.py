"""
train_qlora.py
---------------
QLoRA fine-tuning of Qwen2.5-7B-Instruct on the Egyptian law dataset built
by data_prep.py, tuned to fit an 8GB consumer GPU (e.g. RTX 5060 8GB).

Memory strategy for 8GB VRAM:
  - Base model loaded in 4-bit NF4 (bitsandbytes) -> ~4.5-5 GB for weights.
  - Only small LoRA adapters are trained -> negligible optimizer memory.
  - Gradient checkpointing -> trades compute for activation memory.
  - Paged 8-bit AdamW optimizer -> avoids optimizer-state VRAM spikes.
  - Small per-device batch size + gradient accumulation for an effective
    larger batch without the memory cost.
  - Modest max_seq_length (768) to bound activation memory.

Run:
    python train_qlora.py
"""

import os

# Must be set before torch/CUDA initializes anything.
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

from pathlib import Path

import torch
from datasets import load_dataset
from peft import LoraConfig
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)
from trl import SFTConfig, SFTTrainer
import trl
import inspect

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "data" / "finetune_dataset.jsonl"
OUTPUT_DIR = BASE_DIR / "qwen-legal-qlora"

MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"
MAX_SEQ_LENGTH = 768        # lower to 512 first if you still hit CUDA OOM

LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
LORA_TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj",
]

PER_DEVICE_BATCH_SIZE = 1
GRAD_ACCUMULATION_STEPS = 16   # effective batch size = 1 * 16 = 16
NUM_EPOCHS = 1
LEARNING_RATE = 2e-4


def main():
    print(f"[*] trl version: {trl.__version__}")

    if not DATASET_PATH.exists():
        raise SystemExit(
            f"Dataset not found at '{DATASET_PATH}'. Run data_prep.py first."
        )

    cuda_available = torch.cuda.is_available()
    if not cuda_available:
        raise SystemExit(
            "No CUDA GPU detected. QLoRA fine-tuning of a 7B model on CPU is "
            "impractically slow — this script expects a CUDA GPU."
        )

    bf16_ok = torch.cuda.is_bf16_supported()
    compute_dtype = torch.bfloat16 if bf16_ok else torch.float16
    print(f"[*] Using compute dtype: {compute_dtype}")

    print(f"[*] Loading tokenizer for {MODEL_ID}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print(f"[*] Loading {MODEL_ID} in 4-bit NF4...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
    )
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map={"": 0},
        trust_remote_code=True,
    )
    model.config.use_cache = False  # required alongside gradient checkpointing

    lora_config = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=LORA_TARGET_MODULES,
    )

    print(f"[*] Loading dataset from '{DATASET_PATH}'...")
    dataset = load_dataset("json", data_files=str(DATASET_PATH), split="train")
    print(f"[+] {len(dataset)} training examples loaded.")

    sft_config_kwargs = dict(
        output_dir=str(OUTPUT_DIR),
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LENGTH,
        packing=True,                      # concatenates short examples to fill each sequence
        per_device_train_batch_size=PER_DEVICE_BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUMULATION_STEPS,
        num_train_epochs=NUM_EPOCHS,
        learning_rate=LEARNING_RATE,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        max_grad_norm=0.3,
        optim="paged_adamw_8bit",          # keeps optimizer-state VRAM low
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        bf16=bf16_ok,
        fp16=not bf16_ok,
        logging_steps=5,
        save_strategy="epoch",
        save_total_limit=2,
        report_to="none",
    )

    # Different trl releases have renamed / dropped a few SFTConfig fields
    # over time. Rather than guessing your exact installed version, only
    # pass the kwargs your installed SFTConfig actually accepts, and warn
    # about anything silently dropped.
    valid_params = set(inspect.signature(SFTConfig.__init__).parameters)
    dropped = [k for k in sft_config_kwargs if k not in valid_params]
    if dropped:
        print(f"[!] Your installed trl's SFTConfig does not accept these fields "
              f"(skipping them): {dropped}")
    sft_config_kwargs = {k: v for k, v in sft_config_kwargs.items() if k in valid_params}

    sft_config = SFTConfig(**sft_config_kwargs)

    # Confirm what actually landed, since a silently-dropped max_seq_length
    # or packing setting would blow past the VRAM budget this script is tuned for.
    print(f"[*] Effective max_seq_length: {getattr(sft_config, 'max_seq_length', 'NOT SET — check your trl version!')}")
    print(f"[*] Effective packing: {getattr(sft_config, 'packing', 'NOT SET')}")

    trainer_kwargs = dict(
        model=model,
        args=sft_config,
        train_dataset=dataset,
        peft_config=lora_config,
        tokenizer=tokenizer,
        processing_class=tokenizer,
    )
    valid_trainer_params = set(inspect.signature(SFTTrainer.__init__).parameters)
    trainer_kwargs = {k: v for k, v in trainer_kwargs.items() if k in valid_trainer_params}

    trainer = SFTTrainer(**trainer_kwargs)

    print("[*] Trainable parameters:")
    trainer.model.print_trainable_parameters()

    print("\n[*] Starting training...\n")
    trainer.train()

    print(f"[*] Saving LoRA adapter to '{OUTPUT_DIR}'...")
    trainer.save_model(str(OUTPUT_DIR))
    tokenizer.save_pretrained(str(OUTPUT_DIR))

    print("\n[+] Done. The adapter (not a merged model) is saved at:")
    print(f"    {OUTPUT_DIR}")
    print("Load it at inference by attaching it to the 4-bit base model with peft "
          "(see inference_test.py), or merge it into a standalone model with "
          "merge_lora.py.")


if __name__ == "__main__":
    main()