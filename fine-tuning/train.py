"""
train.py — QLoRA SFT training on the dataset produced by prepare_data.py.

Run:
    python train.py

Fixes vs. the earlier multi-file version:
- No resume-from-checkpoint logic. That logic was the direct cause of a
  real bug: after a successful run, re-running this script found the old
  "finished" checkpoint and silently no-op'd (0.006s "training", same
  stale adapter re-saved) instead of doing anything. Now, if models/sft/
  already contains output, it's automatically archived to a timestamped
  folder before training starts fresh -- you can never silently retrain
  into a no-op again.
- optim switched from `paged_adamw_8bit` to `adamw_8bit`: the paged
  variant has a known history of silently hanging on Windows with certain
  bitsandbytes/CUDA driver combinations. Same 8-bit memory savings,
  without the paging behavior that's flaky on Windows.
- `dataloader_num_workers=0` / single-process dataset mapping: Windows'
  multiprocessing model (spawn, not fork) is a known source of DataLoader
  worker hangs that Linux doesn't have.
- `max_seq_length` default lowered to 512 (from 1536/768): your RTX 5060
  (8GB) was spilling into shared system RAM at both those settings (visibly
  confirmed via Task Manager -- Dedicated GPU memory pinned at ~7.5/8GB and
  Shared GPU memory climbing), which caused ~50 minutes/step instead of
  seconds/step. 512 covers the large majority of this dataset's examples
  (short article Q&A / short-answer variants); only the longest
  cloze/recitation examples get truncated. Raise this only if you confirm
  (via Task Manager) that Dedicated GPU memory has real headroom left.
- `remove_unused_columns` fixed to True: the earlier `False` setting left
  the raw `"text"` string column alongside the tokenized columns, which
  crashed the collator with `ValueError: too many dimensions 'str'` when
  it tried to tensor-ify a string. DataCollatorForCompletionOnlyLM only
  needs the tokenized columns.
- `eval_steps` is now computed from the actual dataset size (not a fixed
  25, which never fired in a 10-step run) so evaluation actually happens
  at least a few times during a short run.
- Explicit progress tracking (ProgressCallback below): prints per-step
  timing, elapsed time, and a real ETA on every step, plus an upfront
  warning that step 1 can take several minutes of silence (CUDA kernel
  warm-up) before anything prints -- addresses the earlier confusion
  where a slow-but-working step 1 was indistinguishable from a genuine
  hang with only the default tqdm bar.
"""

import datetime
import os
import shutil
import sys
import time

import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainerCallback
from trl import DataCollatorForCompletionOnlyLM, SFTConfig, SFTTrainer

# ============================================================================
# CONFIG
# ============================================================================
ROOT = os.path.dirname(os.path.abspath(__file__))
SFT_DIR = os.path.join(ROOT, "data", "sft")
MODELS_DIR = os.path.join(ROOT, "models")
SFT_OUTPUT_DIR = os.path.join(MODELS_DIR, "sft")
LOG_DIR = os.path.join(ROOT, "logs")

BASE_MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"
SEED = 42

# VRAM-sensitive -- lower max_seq_length first if you see Shared GPU memory
# climbing in Task Manager (Performance tab -> GPU -> Shared GPU memory).
MAX_SEQ_LENGTH = 512
PER_DEVICE_BATCH_SIZE = 1
GRADIENT_ACCUMULATION_STEPS = 16
NUM_TRAIN_EPOCHS = 1.0          # small dataset -- more epochs risks memorizing template phrasing
LEARNING_RATE = 1.5e-4
MAX_GRAD_NORM = 0.3

# LoRA -- all linear projections, for real domain-knowledge adaptation, not
# just attention-only adaptation which under-adapts factual content.
# If you still OOM after lowering MAX_SEQ_LENGTH, the next lever is
# dropping "gate_proj","up_proj","down_proj" here (attention-only), at the
# cost of weaker domain-knowledge injection.
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
LORA_TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]

for d in (MODELS_DIR, LOG_DIR):
    os.makedirs(d, exist_ok=True)


# ============================================================================
# Progress tracking
# ============================================================================
class ProgressCallback(TrainerCallback):
    """Prints explicit, human-readable progress -- addresses the confusing
    silent gap during step 1 (CUDA kernel warm-up can take minutes with no
    console output otherwise, which looks identical to a genuine hang)."""

    def on_train_begin(self, args, state, control, **kwargs):
        print(f"\n[TRAIN] Starting training -- {state.max_steps} total steps.")
        print("[TRAIN] Step 1 may take several minutes (CUDA warm-up) even "
              "though nothing prints yet -- this is expected, not a hang.")
        self.t0 = time.time()
        self.last_step_time = self.t0

    def on_step_end(self, args, state, control, **kwargs):
        now = time.time()
        step_time = now - self.last_step_time
        self.last_step_time = now
        elapsed = now - self.t0
        remaining_steps = state.max_steps - state.global_step
        eta_sec = step_time * remaining_steps
        print(f"[TRAIN] step {state.global_step}/{state.max_steps} "
              f"({step_time:.1f}s this step, {elapsed/60:.1f}min elapsed, "
              f"ETA {eta_sec/60:.1f}min)")

    def on_evaluate(self, args, state, control, metrics=None, **kwargs):
        if metrics:
            loss = metrics.get("eval_loss", "n/a")
            loss_str = f"{loss:.4f}" if isinstance(loss, float) else str(loss)
            print(f"[EVAL] step {state.global_step}: eval_loss={loss_str}")

    def on_train_end(self, args, state, control, **kwargs):
        print(f"[TRAIN] Finished in {(time.time()-self.t0)/60:.1f} minutes total.")


# ============================================================================
def archive_stale_output():
    """Prevents the resume-into-no-op bug: if models/sft already has
    content, move it aside with a timestamp instead of silently resuming
    (or worse, silently doing nothing) into it."""
    if os.path.isdir(SFT_OUTPUT_DIR) and os.listdir(SFT_OUTPUT_DIR):
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = os.path.join(MODELS_DIR, f"sft_backup_{stamp}")
        print(f"[INFO] Existing output found in {SFT_OUTPUT_DIR} -- "
              f"archiving it to {backup} before training fresh.")
        shutil.move(SFT_OUTPUT_DIR, backup)
    os.makedirs(SFT_OUTPUT_DIR, exist_ok=True)


def build_model_and_tokenizer():
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_ID)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_ID,
        quantization_config=bnb_config,
        device_map={"": 0},
        torch_dtype=torch.bfloat16,
        attn_implementation="sdpa",
    )
    model.config.use_cache = False

    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)

    lora_config = LoraConfig(
        r=LORA_R, lora_alpha=LORA_ALPHA, lora_dropout=LORA_DROPOUT,
        bias="none", task_type="CAUSAL_LM", target_modules=LORA_TARGET_MODULES,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    return model, tokenizer


def main():
    torch.manual_seed(SEED)

    train_path = os.path.join(SFT_DIR, "train.jsonl")
    val_path = os.path.join(SFT_DIR, "val.jsonl")
    if not os.path.exists(train_path):
        print("data/sft/train.jsonl not found. Run prepare_data.py first.")
        sys.exit(1)

    archive_stale_output()

    dataset = load_dataset("json", data_files={
        "train": train_path,
        **({"validation": val_path} if os.path.exists(val_path) else {}),
    })

    n_train = len(dataset["train"])
    steps_per_epoch = max(1, n_train // (PER_DEVICE_BATCH_SIZE * GRADIENT_ACCUMULATION_STEPS))
    total_steps = max(1, int(steps_per_epoch * NUM_TRAIN_EPOCHS))
    eval_steps = max(1, total_steps // 4)   # evaluate ~4 times over the whole run, regardless of run length
    print(f"Train examples: {n_train} | steps/epoch: {steps_per_epoch} | "
          f"total steps: {total_steps} | eval every {eval_steps} steps")

    model, tokenizer = build_model_and_tokenizer()

    response_template = "<|im_start|>assistant\n"
    collator = DataCollatorForCompletionOnlyLM(response_template=response_template, tokenizer=tokenizer)

    def add_text_field(batch):
        return {"text": [
            tokenizer.apply_chat_template(m, tokenize=False, add_generation_prompt=False)
            for m in batch["messages"]
        ]}

    dataset = dataset.map(add_text_field, batched=True, remove_columns=["messages"])

    has_val = "validation" in dataset
    sft_config = SFTConfig(
        output_dir=SFT_OUTPUT_DIR,
        max_seq_length=MAX_SEQ_LENGTH,
        per_device_train_batch_size=PER_DEVICE_BATCH_SIZE,
        per_device_eval_batch_size=PER_DEVICE_BATCH_SIZE,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION_STEPS,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        learning_rate=LEARNING_RATE,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        weight_decay=0.0,
        num_train_epochs=NUM_TRAIN_EPOCHS,
        max_grad_norm=MAX_GRAD_NORM,
        optim="adamw_8bit",
        bf16=True,
        fp16=False,
        eval_strategy="steps" if has_val else "no",
        eval_steps=eval_steps,
        save_strategy="steps",
        save_steps=eval_steps,
        save_total_limit=2,
        load_best_model_at_end=has_val,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        logging_steps=max(1, eval_steps // 5),
        logging_dir=LOG_DIR,
        report_to=["none"],
        seed=SEED,
        packing=False,
        dataset_text_field="text",
        remove_unused_columns=True,   # fixed: was False, which crashed the collator on the raw text column
        dataloader_num_workers=0,     # Windows-safe: avoids spawn-related DataLoader worker hangs
        dataset_num_proc=1,
    )

    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"] if has_val else None,
        data_collator=collator,
        processing_class=tokenizer,
        callbacks=[ProgressCallback()],
    )

    trainer.train()   # always fresh -- see archive_stale_output() above

    trainer.save_model(SFT_OUTPUT_DIR)
    tokenizer.save_pretrained(SFT_OUTPUT_DIR)
    print(f"\nTraining complete. LoRA adapter saved to {SFT_OUTPUT_DIR}")


if __name__ == "__main__":
    main()