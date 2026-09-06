"""
Stage 4: Single-stage QLoRA SFT / domain adaptation.

Why one stage instead of CPT -> SFT:
- CPT (raw next-token prediction on OCR'd book text) needs enough tokens for
  gradient signal to average out into general domain patterns rather than
  memorizing the exact 3 documents. With ~3 books that risk is high, and
  CPT on an *instruction-tuned* checkpoint additionally risks damaging its
  instruction-following behavior before SFT ever gets a chance to restore it.
- Because our SFT set already contains article-recall, cloze/continuation,
  and definition-extraction examples derived directly from the source
  documents (see build_sft_dataset.py), the model gets the same raw-text
  exposure a CPT stage would give it, but under assistant-turn loss and
  wrapped in the instruct chat format the whole time -- so there is no
  "instruction-following regression, then hope SFT fixes it" phase.
- This also sidesteps the CPT-adapter -> merge -> new-SFT-adapter question
  from the brief entirely: there's only one adapter, trained once.

Loss: assistant-only (completion-only) loss via DataCollatorForCompletionOnlyLM,
matching Qwen2.5's chat template turn markers. This is required for chat SFT --
computing loss over the user/system tokens teaches the model to predict
*questions*, which is not the objective.

Quantization: 4-bit NF4 + double quantization (QLoRA), bf16 compute dtype.
RTX 50-series (Blackwell) supports bf16 natively and PyTorch's Blackwell
support requires a very recent build -- see requirements.txt / README.
"""

import os
import sys

import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)
from trl import SFTConfig, SFTTrainer, DataCollatorForCompletionOnlyLM

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    BASE_MODEL_ID, SFT_DIR, SFT_OUTPUT_DIR, LOG_DIR, SEED,
    LORA_CFG, TRAIN_CFG,
)


def build_model_and_tokenizer():
    compute_dtype = getattr(torch, TRAIN_CFG.bnb_4bit_compute_dtype)

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=TRAIN_CFG.load_in_4bit,
        bnb_4bit_quant_type=TRAIN_CFG.bnb_4bit_quant_type,
        bnb_4bit_use_double_quant=TRAIN_CFG.bnb_4bit_use_double_quant,
        bnb_4bit_compute_dtype=compute_dtype,
    )

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_ID)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_ID,
        quantization_config=bnb_config,
        device_map={"": 0},
        torch_dtype=compute_dtype,
        attn_implementation="sdpa",  # broadly compatible; flash-attn2 build for Blackwell is often unavailable yet
    )
    model.config.use_cache = False  # required alongside gradient checkpointing

    model = prepare_model_for_kbit_training(
        model, use_gradient_checkpointing=TRAIN_CFG.gradient_checkpointing
    )

    lora_config = LoraConfig(
        r=LORA_CFG.r,
        lora_alpha=LORA_CFG.alpha,
        lora_dropout=LORA_CFG.dropout,
        bias=LORA_CFG.bias,
        task_type=LORA_CFG.task_type,
        target_modules=LORA_CFG.target_modules,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    return model, tokenizer


def formatting_func(example, tokenizer):
    return tokenizer.apply_chat_template(
        example["messages"], tokenize=False, add_generation_prompt=False
    )


def main():
    torch.manual_seed(SEED)

    train_path = os.path.join(SFT_DIR, "train.jsonl")
    val_path = os.path.join(SFT_DIR, "val.jsonl")
    if not os.path.exists(train_path):
        print("data/sft/train.jsonl not found. Run scripts/build_sft_dataset.py "
              "and scripts/validate_dataset.py first.")
        sys.exit(1)

    dataset = load_dataset("json", data_files={
        "train": train_path,
        **({"validation": val_path} if os.path.exists(val_path) else {}),
    })

    model, tokenizer = build_model_and_tokenizer()

    # Qwen2.5's chat template marks each turn with "<|im_start|>{role}\n ... <|im_end|>"
    # -- mask everything before the assistant turn so loss is completion-only.
    response_template = "<|im_start|>assistant\n"
    collator = DataCollatorForCompletionOnlyLM(
        response_template=response_template,
        tokenizer=tokenizer,
    )

    sft_config = SFTConfig(
        output_dir=SFT_OUTPUT_DIR,
        max_seq_length=TRAIN_CFG.max_seq_length,
        per_device_train_batch_size=TRAIN_CFG.per_device_train_batch_size,
        per_device_eval_batch_size=TRAIN_CFG.per_device_eval_batch_size,
        gradient_accumulation_steps=TRAIN_CFG.gradient_accumulation_steps,
        gradient_checkpointing=TRAIN_CFG.gradient_checkpointing,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        learning_rate=TRAIN_CFG.learning_rate,
        lr_scheduler_type=TRAIN_CFG.lr_scheduler_type,
        warmup_ratio=TRAIN_CFG.warmup_ratio,
        weight_decay=TRAIN_CFG.weight_decay,
        num_train_epochs=TRAIN_CFG.num_train_epochs,
        max_grad_norm=TRAIN_CFG.max_grad_norm,
        optim=TRAIN_CFG.optim,
        bf16=TRAIN_CFG.bf16,
        fp16=TRAIN_CFG.fp16,
        eval_strategy=TRAIN_CFG.eval_strategy if "validation" in dataset else "no",
        eval_steps=TRAIN_CFG.eval_steps,
        save_strategy=TRAIN_CFG.save_strategy,
        save_steps=TRAIN_CFG.save_steps,
        save_total_limit=TRAIN_CFG.save_total_limit,
        load_best_model_at_end=TRAIN_CFG.load_best_model_at_end if "validation" in dataset else False,
        metric_for_best_model=TRAIN_CFG.metric_for_best_model,
        greater_is_better=TRAIN_CFG.greater_is_better,
        logging_steps=TRAIN_CFG.logging_steps,
        logging_dir=LOG_DIR,
        report_to=["none"],
        seed=SEED,
        packing=TRAIN_CFG.packing,
        dataset_text_field="text",
        remove_unused_columns=True,
    )

    # Pre-render the chat-template text field the collator expects.
    def add_text_field(batch):
        return {"text": [
            tokenizer.apply_chat_template(m, tokenize=False, add_generation_prompt=False)
            for m in batch["messages"]
        ]}

    dataset = dataset.map(add_text_field, batched=True, remove_columns=["messages"])

    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"] if "validation" in dataset else None,
        data_collator=collator,
        processing_class=tokenizer,
    )

    resume = os.path.isdir(SFT_OUTPUT_DIR) and any(
        f.startswith("checkpoint-") for f in os.listdir(SFT_OUTPUT_DIR)
    )
    trainer.train(resume_from_checkpoint=resume)

    trainer.save_model(SFT_OUTPUT_DIR)
    tokenizer.save_pretrained(SFT_OUTPUT_DIR)
    print(f"\nTraining complete. LoRA adapter saved to {SFT_OUTPUT_DIR}")


if __name__ == "__main__":
    main()
