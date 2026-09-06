"""
run.py — inference. CLI chat by default; also exposes load_model()/ask()
as a clean, stable interface for a future backend to import directly.

Run:
    python run.py                     # chat, adapter mode
    python run.py --mode merged --merge   # merge once, then chat

Backend handoff (see conversation history): import load_model() once at
server startup, call ask(handle, messages) per request. Caller owns
conversation history (pass the full message list each call); caller must
serialize concurrent calls (single GPU, single model instance).
"""

import argparse
import os

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

ROOT = os.path.dirname(os.path.abspath(__file__))
SFT_OUTPUT_DIR = os.path.join(ROOT, "models", "sft")
MERGED_DIR = os.path.join(ROOT, "models", "merged")
BASE_MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"

SYSTEM_PROMPT = (
    "أنت مساعد قانوني متخصص في القانون. أجب بدقة استنادًا إلى المعرفة القانونية "
    "التي تم تدريبك عليها، واذكر رقم المادة عند الإمكان."
)
MAX_NEW_TOKENS = 512
TEMPERATURE = 0.3
TOP_P = 0.9
REPETITION_PENALTY = 1.1


# ============================================================================
# Loading
# ============================================================================
def load_adapter_model():
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16,
    )
    tokenizer = AutoTokenizer.from_pretrained(SFT_OUTPUT_DIR)
    base = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_ID, quantization_config=bnb_config, device_map={"": 0}, torch_dtype=torch.bfloat16,
    )
    model = PeftModel.from_pretrained(base, SFT_OUTPUT_DIR)
    model.eval()
    return model, tokenizer


def merge_and_save():
    tokenizer = AutoTokenizer.from_pretrained(SFT_OUTPUT_DIR)
    base = AutoModelForCausalLM.from_pretrained(BASE_MODEL_ID, torch_dtype=torch.bfloat16, device_map="cpu")
    model = PeftModel.from_pretrained(base, SFT_OUTPUT_DIR)
    merged = model.merge_and_unload()
    os.makedirs(MERGED_DIR, exist_ok=True)
    merged.save_pretrained(MERGED_DIR, safe_serialization=True)
    tokenizer.save_pretrained(MERGED_DIR)
    print(f"Merged model saved to {MERGED_DIR}")


def load_merged_model():
    tokenizer = AutoTokenizer.from_pretrained(MERGED_DIR)
    model = AutoModelForCausalLM.from_pretrained(MERGED_DIR, torch_dtype=torch.bfloat16, device_map={"": 0})
    model.eval()
    return model, tokenizer


def load_model(mode: str = "adapter"):
    """Call ONCE at process/server startup. Returns a model handle used by ask()."""
    if mode == "adapter":
        model, tokenizer = load_adapter_model()
    else:
        if not os.path.isdir(MERGED_DIR):
            merge_and_save()
        model, tokenizer = load_merged_model()
    return {"model": model, "tokenizer": tokenizer}


# ============================================================================
# Inference
# ============================================================================
def ask(handle: dict, messages: list) -> str:
    """messages = [{"role": "user"/"assistant", "content": str}, ...]
    (system prompt is added automatically). Returns the assistant's reply
    as a plain string. Caller owns conversation history and must serialize
    concurrent calls -- one GPU, one model instance."""
    model, tokenizer = handle["model"], handle["tokenizer"]
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    prompt = tokenizer.apply_chat_template(full_messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            temperature=TEMPERATURE,
            top_p=TOP_P,
            repetition_penalty=REPETITION_PENALTY,
            do_sample=True,
            pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
        )
    new_tokens = output_ids[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()


# ============================================================================
# CLI chat
# ============================================================================
def chat_loop(handle):
    print("Arabic legal assistant ready. Type 'exit' to quit.\n")
    history = []
    while True:
        question = input("السؤال: ").strip()
        if question.lower() in {"exit", "quit"}:
            break
        history.append({"role": "user", "content": question})
        answer = ask(handle, history)
        print(f"\nالإجابة: {answer}\n")
        history.append({"role": "assistant", "content": answer})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["adapter", "merged"], default="adapter")
    parser.add_argument("--merge", action="store_true", help="(re)run the merge step before chatting in merged mode")
    args = parser.parse_args()

    if args.mode == "merged" and args.merge:
        merge_and_save()

    handle = load_model(mode=args.mode)
    chat_loop(handle)


if __name__ == "__main__":
    main()
