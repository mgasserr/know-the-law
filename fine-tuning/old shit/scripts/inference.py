"""
Stage 5: Inference.

Two modes:
  --mode adapter (default): load the base model in 4-bit + the LoRA adapter
      on top. Lower disk usage, slightly slower per-token, and lets you swap
      adapters without re-downloading the base model. Recommended for
      day-to-day use and for iterating on further fine-tuning.
  --mode merged: merge the LoRA weights into the base model once (in fp16,
      not 4-bit, so this needs ~16GB free RAM/disk during the merge, not
      VRAM) and save a standalone model. Slightly faster inference and
      simpler to hand off/deploy, at the cost of a larger artifact on disk
      and having to re-merge if you retrain the adapter.

Usage:
    python scripts/inference.py --mode adapter
    python scripts/inference.py --mode merged --merge   # merges once, then chats
"""

import argparse
import os
import sys

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import BASE_MODEL_ID, SFT_OUTPUT_DIR, MODELS_DIR, INFER_CFG, TRAIN_CFG

MERGED_DIR = os.path.join(MODELS_DIR, "merged")


def load_adapter_model():
    # 1. Load the base tokenizer and base model
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_ID)
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_ID,
        device_map="auto",
        torch_dtype=torch.float16, # or bfloat16
    )
    
    # 2. Apply the LoRA adapter on top of the base model
    model = PeftModel.from_pretrained(base_model, SFT_OUTPUT_DIR)
    
    return model, tokenizer

def merge_and_save():
    tokenizer = AutoTokenizer.from_pretrained(SFT_OUTPUT_DIR)
    base = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_ID, torch_dtype=torch.bfloat16, device_map="cpu",
    )
    model = PeftModel.from_pretrained(base, SFT_OUTPUT_DIR)
    merged = model.merge_and_unload()
    os.makedirs(MERGED_DIR, exist_ok=True)
    merged.save_pretrained(MERGED_DIR, safe_serialization=True)
    tokenizer.save_pretrained(MERGED_DIR)
    print(f"Merged model saved to {MERGED_DIR}")


def load_merged_model():
    tokenizer = AutoTokenizer.from_pretrained(MERGED_DIR)
    model = AutoModelForCausalLM.from_pretrained(
        MERGED_DIR, torch_dtype=torch.bfloat16, device_map={"": 0},
    )
    model.eval()
    return model, tokenizer


def chat_loop(model, tokenizer):
    print("Arabic legal assistant ready. Type 'exit' to quit.\n")
    history = [{"role": "system", "content": INFER_CFG.system_prompt}]
    while True:
        question = input("السؤال: ").strip()
        if question.lower() in {"exit", "quit"}:
            break
        history.append({"role": "user", "content": question})
        prompt = tokenizer.apply_chat_template(
            history, tokenize=False, add_generation_prompt=True
        )
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=INFER_CFG.max_new_tokens,
                temperature=INFER_CFG.temperature,
                top_p=INFER_CFG.top_p,
                repetition_penalty=INFER_CFG.repetition_penalty,
                do_sample=True,
                pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
            )
        new_tokens = output_ids[0][inputs["input_ids"].shape[1]:]
        answer = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
        print(f"\nالإجابة: {answer}\n")
        history.append({"role": "assistant", "content": answer})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["adapter", "merged"], default="adapter")
    parser.add_argument("--merge", action="store_true", help="(re)run the merge step before chatting in merged mode")
    args = parser.parse_args()

    if args.mode == "adapter":
        model, tokenizer = load_adapter_model()
    else:
        if args.merge or not os.path.isdir(MERGED_DIR):
            merge_and_save()
        model, tokenizer = load_merged_model()

    chat_loop(model, tokenizer)


if __name__ == "__main__":
    main()
