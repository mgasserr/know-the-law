"""
Stage 3.5: Validate everything before spending GPU time on training.

Run this after build_sft_dataset.py and before train_sft.py.
Exits with a non-zero status (and refuses to let you proceed) if a
catastrophic problem is found (empty dataset, missing fields, etc).
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import PDF_DIR, OCR_DIR, PROCESSED_DIR, SFT_DIR, BASE_MODEL_ID


def fail(msg):
    print(f"[FAIL] {msg}")
    sys.exit(1)


def warn(msg):
    print(f"[WARN] {msg}")


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    print("=== 1. PDFs ===")
    pdfs = [f for f in os.listdir(PDF_DIR) if f.lower().endswith(".pdf")]
    if not pdfs:
        fail(f"No PDFs in {PDF_DIR}.")
    for p in pdfs:
        path = os.path.join(PDF_DIR, p)
        if os.path.getsize(path) == 0:
            fail(f"{p} is empty/unreadable.")
    print(f"Found {len(pdfs)} PDF(s): {pdfs}")

    print("\n=== 2. OCR output ===")
    ocr_files = [f for f in os.listdir(OCR_DIR) if f.endswith(".jsonl")] if os.path.isdir(OCR_DIR) else []
    if not ocr_files:
        fail("No OCR output found. Run scripts/ocr.py first.")
    total_pages, failed_pages, total_chars = 0, 0, 0
    for f in ocr_files:
        records = load_jsonl(os.path.join(OCR_DIR, f))
        total_pages += len(records)
        for r in records:
            total_chars += len(r.get("raw_text", ""))
            if len(r.get("raw_text", "")) < 20:
                failed_pages += 1
    print(f"OCR files: {len(ocr_files)} | total pages: {total_pages} | "
          f"pages with near-empty OCR: {failed_pages} | total raw chars: {total_chars}")
    if total_pages == 0:
        fail("OCR produced zero pages.")
    if failed_pages / max(total_pages, 1) > 0.5:
        warn("More than half of pages had near-empty OCR output -- check scan "
             "quality/DPI/orientation before proceeding.")

    print("\n=== 3. Processed corpus / articles ===")
    corpus_path = os.path.join(PROCESSED_DIR, "corpus.jsonl")
    articles_path = os.path.join(PROCESSED_DIR, "articles.jsonl")
    if not os.path.exists(corpus_path):
        fail("data/processed/corpus.jsonl missing. Run scripts/clean_dataset.py.")
    corpus = load_jsonl(corpus_path)
    articles = load_jsonl(articles_path) if os.path.exists(articles_path) else []
    if not corpus:
        fail("Processed corpus is empty -- quality filtering rejected every page. "
             "Check data/processed/ocr_quality_report.csv.")
    print(f"Kept pages: {len(corpus)} | Extracted articles: {len(articles)}")
    if not articles:
        warn("Zero legal articles were detected. The dataset will fall back to "
             "recitation-only examples, which is weaker for grounded Q&A. "
             "Consider checking the article heading regex.")

    print("\n=== 4. SFT dataset ===")
    train_path = os.path.join(SFT_DIR, "train.jsonl")
    val_path = os.path.join(SFT_DIR, "val.jsonl")
    if not os.path.exists(train_path):
        fail("data/sft/train.jsonl missing. Run scripts/build_sft_dataset.py.")
    train = load_jsonl(train_path)
    val = load_jsonl(val_path) if os.path.exists(val_path) else []
    if not train:
        fail("Training set is empty.")

    lengths, bad = [], 0
    for ex in train + val:
        msgs = ex.get("messages")
        if not msgs or len(msgs) < 2:
            bad += 1
            continue
        roles = [m["role"] for m in msgs]
        if "assistant" not in roles or "user" not in roles:
            bad += 1
            continue
        lengths.append(sum(len(m["content"]) for m in msgs))
    if bad:
        fail(f"{bad} malformed examples (missing required message fields).")

    # duplicate check (exact user+assistant match)
    seen = set()
    dup_count = 0
    for ex in train:
        key = json.dumps(ex["messages"], ensure_ascii=False)
        if key in seen:
            dup_count += 1
        seen.add(key)

    print(f"Train examples: {len(train)} | Val examples: {len(val)}")
    print(f"Exact-duplicate train examples: {dup_count}")
    print(f"Avg chars/example: {sum(lengths)/len(lengths):.0f} | "
          f"min: {min(lengths)} | max: {max(lengths)}")

    print("\n=== 5. Tokenizer sanity check ===")
    try:
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained(BASE_MODEL_ID)
        sample = train[0]["messages"]
        rendered = tok.apply_chat_template(sample, tokenize=False, add_generation_prompt=False)
        n_tokens = len(tok(rendered)["input_ids"])
        print(f"Chat template renders OK. Sample token length: {n_tokens}")
    except Exception as e:  # noqa: BLE001
        warn(f"Could not load tokenizer / apply chat template ({e}). "
             "This will need to succeed before training can run.")

    print("\nValidation complete. Dataset looks trainable." if train else "Validation FAILED.")


if __name__ == "__main__":
    main()
