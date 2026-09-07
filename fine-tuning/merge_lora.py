"""
merge_lora.py
-------------
OPTIONAL. Merges the LoRA adapter into a standalone fp16 model on disk —
useful if you want to convert to GGUF for llama.cpp/Ollama, or ship a
single model folder without needing peft at inference time.

You almost certainly do NOT need this for your RAG backend: loading the
4-bit base model + adapter directly (see inference_test.py / RAG.py) is
lighter on VRAM and works fine as-is.

Note: merging requires loading the base model in fp16 (not 4-bit), which
does NOT fit in 8GB VRAM for a 7B model. This script loads it on CPU
instead — it needs ~14-16GB of system RAM and will take several minutes,
but does not touch the GPU.

Run:
    python merge_lora.py
"""

from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = BASE_DIR / "qwen-legal-qlora"
MERGED_OUTPUT_DIR = BASE_DIR / "qwen-legal-merged"

MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"


def main():
    if not ADAPTER_DIR.exists():
        raise SystemExit(
            f"No adapter found at '{ADAPTER_DIR}'. Run train_qlora.py first."
        )

    print(f"[*] Loading base model {MODEL_ID} on CPU in fp16 (this is slow)...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    base_model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16,
        device_map="cpu",
        trust_remote_code=True,
    )

    print(f"[*] Attaching adapter from '{ADAPTER_DIR}'...")
    model = PeftModel.from_pretrained(base_model, str(ADAPTER_DIR))

    print("[*] Merging LoRA weights into the base model...")
    model = model.merge_and_unload()

    MERGED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[*] Saving merged model to '{MERGED_OUTPUT_DIR}'...")
    model.save_pretrained(str(MERGED_OUTPUT_DIR))
    tokenizer.save_pretrained(str(MERGED_OUTPUT_DIR))

    print("\n[+] Done. Merged, standalone model saved at:")
    print(f"    {MERGED_OUTPUT_DIR}")


if __name__ == "__main__":
    main()
