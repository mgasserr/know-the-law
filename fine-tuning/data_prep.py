"""
data_prep.py
------------
Extracts text from the 3 project PDFs, cleans OCR artifacts (same regex
rules used in the RAG backend), splits them into training-sized chunks,
and wraps each chunk in the model's chat template so the fine-tune keeps
the same conversational structure used at inference time.

Output: ./data/finetune_dataset.jsonl  (one {"text": "..."} per line)

Run:
    python data_prep.py
"""

import json
import re
from pathlib import Path

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from transformers import AutoTokenizer

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
BASE_DIR = Path(__file__).resolve().parent          # .../know-the-law/fine-tuning
DATA_DIR = BASE_DIR.parent / "data"                 # .../know-the-law/data (same PDFs as the backend)
OUTPUT_PATH = BASE_DIR / "data" / "finetune_dataset.jsonl"

MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"

PDF_PATHS = [
    DATA_DIR / "qanoon el madany summarized.pdf",
    DATA_DIR / "mo5tarat mn a7kam el naqd.pdf",
    DATA_DIR / "mabade2 qanoneya sadera 3n ma7kamet el naqd.pdf",
]

CHUNK_SIZE = 1100
CHUNK_OVERLAP = 0          # no overlap needed for pretraining-style packing
MIN_CHUNK_CHARS = 80       # drop near-empty trailing chunks

# Keep this separate from the RAG backend's SYSTEM_PROMPT: at inference the
# RAG prompt expects retrieved excerpts in the user turn, but here we are
# teaching raw legal text with no retrieved context, so a plain identity
# prompt avoids training the model on a contradictory pattern.
FT_SYSTEM_PROMPT = (
    "أنت مساعد قانوني مصري متخصص في القانون المدني المصري وأحكام محكمة النقض "
    "ومبادئها القانونية."
)
FT_INSTRUCTION = "اعرض بدقة النص القانوني التالي من مصادر القانون المصري:"


def clean_text(text: str) -> str:
    """Same OCR/article-number scrubbing used in the RAG backend, for consistency."""
    text = re.sub(r"مادة\s*\$\((\d+)\)-(\d+)\$?", r"مادة \2 (\1)", text)
    text = re.sub(r"مادة\s*\$?[a-zA-Z]?\s*-?\s*(\d+)", r"مادة \1", text)
    return text.replace("$", "")


def load_and_chunk() -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""],
    )

    chunks: list[str] = []
    for pdf_path in PDF_PATHS:
        if not pdf_path.exists():
            print(f"[!] Warning: '{pdf_path}' not found. Skipping.")
            continue

        print(f"[*] Loading '{pdf_path.name}'...")
        docs = PyMuPDFLoader(str(pdf_path)).load()
        for doc in docs:
            doc.page_content = clean_text(doc.page_content)

        split_docs = splitter.split_documents(docs)
        for d in split_docs:
            stripped = d.page_content.strip()
            if len(stripped) >= MIN_CHUNK_CHARS:
                chunks.append(stripped)

        print(f"    -> {len(split_docs)} chunks from this file.")

    return chunks


def build_chat_examples(chunks: list[str], tokenizer) -> list[str]:
    """Wrap each raw chunk in the chat template as an assistant turn."""
    examples = []
    for chunk in chunks:
        messages = [
            {"role": "system", "content": FT_SYSTEM_PROMPT},
            {"role": "user", "content": FT_INSTRUCTION},
            {"role": "assistant", "content": chunk},
        ]
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=False
        )
        examples.append(text)
    return examples


def main():
    print(f"[*] Loading tokenizer for {MODEL_ID}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)

    chunks = load_and_chunk()
    if not chunks:
        raise SystemExit(
            "No text extracted from the PDFs. Check that the 3 files exist under "
            f"'{DATA_DIR}'."
        )
    print(f"[+] Extracted {len(chunks)} usable chunks total.")

    examples = build_chat_examples(chunks, tokenizer)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for text in examples:
            f.write(json.dumps({"text": text}, ensure_ascii=False) + "\n")

    print(f"[+] Wrote {len(examples)} training examples to '{OUTPUT_PATH}'")


if __name__ == "__main__":
    main()
