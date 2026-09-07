"""
inference_test.py
------------------
Loads the 4-bit base model with the fine-tuned LoRA adapter on top (no
merging needed) and runs a couple of sample legal questions, so you can
sanity-check the fine-tune before wiring it into the RAG backend.

Run:
    python inference_test.py
"""

import os

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

BASE_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = BASE_DIR / "qwen-legal-qlora"
MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"

SYSTEM_PROMPT = (
    "أنت مساعد قانوني مصري متخصص في القانون المدني المصري وأحكام محكمة النقض "
    "ومبادئها القانونية."
)

TEST_QUESTIONS = [
    "ما هي شروط صحة العقد في القانون المدني المصري؟",
    "متى تقع المسؤولية الجنائية والمدنية على الطبيب؟",
]


def main():
    if not ADAPTER_DIR.exists():
        raise SystemExit(
            f"No adapter found at '{ADAPTER_DIR}'. Run train_qlora.py first."
        )

    compute_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16

    print(f"[*] Loading base model {MODEL_ID} in 4-bit...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
    )
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    base_model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map={"": 0},
        trust_remote_code=True,
    )

    print(f"[*] Attaching LoRA adapter from '{ADAPTER_DIR}'...")
    model = PeftModel.from_pretrained(base_model, str(ADAPTER_DIR))
    model.eval()

    for question in TEST_QUESTIONS:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]
        prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=350,
                temperature=0.2,
                do_sample=True,
            )

        full_text = tokenizer.decode(output_ids[0], skip_special_tokens=False)
        answer = full_text.split("<|im_start|>assistant")[-1]
        answer = answer.replace("<|im_end|>", "").strip()

        print("\n" + "=" * 70)
        print(f"السؤال: {question}")
        print("-" * 70)
        print(answer)

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
