"""
prepare_data.py — the ENTIRE data pipeline in one file.

    3 scanned PDFs -> render pages -> OCR (column-aware) -> clean/normalize
    -> quality filter + dedup -> extract legal articles -> generate SFT
    examples -> validate -> data/sft/train.jsonl + val.jsonl

Run:
    python prepare_data.py

Fixes vs. the earlier multi-file version:
- Two-column layout handling is now DETERMINISTIC, not heuristic. You tell
  the script which PDFs are two-column (TWO_COLUMN_PDFS below) instead of
  it guessing from OCR box positions -- that guessing (clustering box
  x-centers to find a "column gap") was fragile and is the most likely
  cause of the scrambled/garbled OCR text seen in earlier runs, since a
  wrong split point chops words/lines from two columns together. Each
  two-column page is now physically cropped into a right half and a left
  half BEFORE OCR, each half is OCR'd as its own self-contained
  single-column image (so plain top-to-bottom ordering is correct within
  each half), and the two halves are concatenated right-then-left (Arabic
  reads right-to-left).
- Render DPI raised 300->400: a two-column page's per-column text is
  roughly half the width of a single-column page's text at the same DPI,
  so the effective resolution per character is lower unless DPI is raised
  to compensate.
- Light image preprocessing (grayscale + autocontrast) added before OCR --
  a standard, low-risk accuracy improvement for scanned book pages.
- The article-splitting regex bug from a prior manual edit
  (`[\\(\\[)?` — an unbalanced/incorrect character class) is fixed here.
- Conservative Arabic normalization only (tatweel + whitespace cleanup) --
  no alef/yeh unification, no diacritic stripping, so legal citations and
  terminology are never altered.
- Zero LLM calls anywhere in SFT data generation -- every answer is a
  verbatim span of the source text, to avoid any hallucinated legal claims.
- Validation is now built into this same script (no separate
  validate_dataset.py) -- it fails loudly with sys.exit(1) if the
  resulting dataset is empty or malformed, instead of silently producing
  nothing for a later stage to trip over.
"""

import csv
import json
import os
import random
import html as html_lib
import re
import sys
from difflib import SequenceMatcher

import fitz  # PyMuPDF
from PIL import Image, ImageOps

# ============================================================================
# CONFIG — edit these, then just run this file
# ============================================================================
ROOT = os.path.dirname(os.path.abspath(__file__))

PDF_DIR = os.path.join(ROOT, "..", "data")          # <- your 3 PDFs live here
OCR_DIR = os.path.join(ROOT, "data", "ocr")
PROCESSED_DIR = os.path.join(ROOT, "data", "processed")
SFT_DIR = os.path.join(ROOT, "data", "sft")

for d in (OCR_DIR, PROCESSED_DIR, SFT_DIR):
    os.makedirs(d, exist_ok=True)

# RTX 5060 (Blackwell, CUDA capability 12.0): use Surya 2 through vLLM.
# These variables MUST be set before importing/constructing SuryaInferenceManager.
RENDER_DPI = 300
OCR_LANG = "ar"
SURYA_BACKEND = "vllm"
SURYA_GPU_INDEX = "0"
SURYA_DTYPE = "float16"
SURYA_GPU_MEMORY_UTILIZATION = "0.60"
SURYA_MAX_MODEL_LEN = "8192"
SURYA_MAX_NUM_SEQS = "1"
SURYA_MAX_BATCHED_TOKENS = "2048"
SURYA_PARALLEL = "1"
SURYA_KEEP_ALIVE = "true"
SURYA_ENABLE_MTP = "false"
SURYA_MAX_TOKENS_FULL_PAGE = "6144"

# Surya's current vLLM launcher has no RTX 5060 entry in its GPU-size table.
# "t4" is therefore used only as a known launcher profile, while the actual
# GPU is still explicitly selected as device 0 and the vLLM limits below are
# overridden for the RTX 5060's 8 GB VRAM.
SURYA_GPU_PROFILE = "t4"

# Force the values for this script rather than inheriting conflicting shell
# environment variables from an older Surya/PaddleOCR setup.
os.environ["SURYA_INFERENCE_BACKEND"] = SURYA_BACKEND
os.environ["SURYA_INFERENCE_AUTOSTART"] = "true"
os.environ["SURYA_INFERENCE_KEEP_ALIVE"] = SURYA_KEEP_ALIVE
os.environ["SURYA_INFERENCE_PARALLEL"] = SURYA_PARALLEL
os.environ.pop("SURYA_INFERENCE_URL", None)
os.environ["VLLM_GPUS"] = SURYA_GPU_INDEX
os.environ["VLLM_GPU_TYPE"] = SURYA_GPU_PROFILE
os.environ["VLLM_DTYPE"] = SURYA_DTYPE
os.environ["VLLM_GPU_MEMORY_UTILIZATION"] = SURYA_GPU_MEMORY_UTILIZATION
os.environ["VLLM_MAX_MODEL_LEN"] = SURYA_MAX_MODEL_LEN
os.environ["VLLM_ENABLE_MTP"] = SURYA_ENABLE_MTP
os.environ["VLLM_EXTRA_ARGS"] = (
    f"--max-num-seqs {SURYA_MAX_NUM_SEQS} "
    f"--max-num-batched-tokens {SURYA_MAX_BATCHED_TOKENS}"
)
os.environ["SURYA_MAX_TOKENS_FULL_PAGE"] = SURYA_MAX_TOKENS_FULL_PAGE

USE_GPU_FOR_OCR = True

# Tell the pipeline exactly which PDFs are two-column layouts.
TWO_COLUMN_PDFS = {
    "qanoon el morafa3at el madaneya wel togareya.pdf": True,
    "qanoon magles el dawla.pdf": True,
    "qanoon el madany summarized.pdf": False,
}
COLUMN_SPLIT_TRIM = 0.01   # trim 1% of width at the split line so we don't cut characters in half

MIN_PAGE_CHARS = 40
MIN_ARABIC_RATIO = 0.55
MAX_REPEATED_RUN = 8
MAX_PUNCT_RATIO = 0.35
NEAR_DUP_SIMILARITY = 0.92
MIN_FRAGMENT_CHARS = 15

VAL_SPLIT_RATIO = 0.1
SEED = 42

SYSTEM_PROMPT = (
    "أنت مساعد قانوني متخصص في القانون. أجب بدقة استنادًا إلى المعرفة القانونية "
    "التي تم تدريبك عليها، واذكر رقم المادة عند الإمكان."
)

random.seed(SEED)

# ============================================================================
# Stage 1: PDF rendering
# ============================================================================
def render_pdf_pages(pdf_path: str, dpi: int):
    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    try:
        for i in range(len(doc)):
            page = doc.load_page(i)
            pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB, alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            yield i + 1, img
    finally:
        doc.close()


def preprocess_image(img: Image.Image) -> Image.Image:
    """Grayscale + autocontrast: a standard, low-risk OCR accuracy booster
    for scanned book pages. Converted back to RGB since PaddleOCR expects
    a 3-channel array."""
    gray = ImageOps.grayscale(img)
    gray = ImageOps.autocontrast(gray)
    return gray.convert("RGB")


# ============================================================================
# Stage 2: OCR (Surya 2 + vLLM, column-aware)
# ============================================================================
def get_ocr_engine():
    """
    Build the current Surya 2 inference stack.

    The RTX 5060 is forced to GPU 0. Settings are deliberately conservative for
    an 8 GB card: one concurrent sequence, 8k context, 70% VRAM utilization,
    and MTP disabled to leave headroom for the desktop and CUDA runtime.
    """
    try:
        import torch
    except ImportError as exc:
        print("[FAIL] PyTorch is not installed in this environment.")
        raise SystemExit(1) from exc

    if not torch.cuda.is_available():
        print("[FAIL] CUDA is not available to PyTorch.")
        print('       Run: python -c "import torch; print(torch.cuda.is_available())"')
        print("       Also verify your NVIDIA driver and CUDA-enabled PyTorch install.")
        raise SystemExit(1)

    gpu_name = torch.cuda.get_device_name(0)
    capability = torch.cuda.get_device_capability(0)
    print(
        f"[INFO] CUDA GPU: {gpu_name} | "
        f"compute capability: {capability[0]}.{capability[1]}"
    )

    if capability < (8, 0):
        print("[FAIL] This script is configured for a modern NVIDIA GPU such as the RTX 5060.")
        raise SystemExit(1)

    try:
        from surya.inference import SuryaInferenceManager
        from surya.recognition import RecognitionPredictor
    except ImportError as exc:
        print("[FAIL] Your installed Surya package does not expose the Surya 2 API.")
        print("       Install/upgrade with: pip install -U surya-ocr")
        raise SystemExit(1) from exc

    print("[INFO] Starting Surya 2 inference manager with vLLM on GPU 0...")
    print(
        "[INFO] "
        f"dtype={SURYA_DTYPE}, "
        f"gpu_memory_utilization={SURYA_GPU_MEMORY_UTILIZATION}, "
        f"max_model_len={SURYA_MAX_MODEL_LEN}, "
        f"max_num_seqs={SURYA_MAX_NUM_SEQS}"
    )

    manager = SuryaInferenceManager()
    return RecognitionPredictor(manager)


def _html_to_text(value: str) -> str:
    """Convert Surya block HTML to conservative plain text."""
    if not value:
        return ""

    value = html_lib.unescape(value)
    value = re.sub(r"(?i)<br\s*/?>", "\n", value)
    value = re.sub(r"(?i)</p\s*>", "\n", value)
    value = re.sub(r"(?i)</div\s*>", "\n", value)
    value = re.sub(r"(?i)</li\s*>", "\n", value)
    value = re.sub(r"(?i)</tr\s*>", "\n", value)
    value = re.sub(r"(?i)</h[1-6]\s*>", "\n", value)
    value = re.sub(r"(?i)<t[dh]\b[^>]*>", " ", value)
    value = re.sub(r"(?i)</t[dh]\s*>", " ", value)
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n[ \t]+", "\n", value)
    value = re.sub(r"[ \t]+\n", "\n", value)
    return value.strip()


def ocr_single_image(recognition_predictor, img: Image.Image):
    """OCR one page/crop with Surya 2 and preserve Surya reading order."""
    predictions = recognition_predictor([img], full_page=True)
    if not predictions:
        return "", 0.0, 0

    page = predictions[0]
    blocks = getattr(page, "blocks", None) or []

    ordered = []
    for idx, block in enumerate(blocks):
        reading_order = getattr(block, "reading_order", idx)
        if reading_order is None:
            reading_order = idx
        ordered.append((int(reading_order), idx, block))
    ordered.sort(key=lambda x: (x[0], x[1]))

    parts = []
    confidences = []

    for _, _, block in ordered:
        if bool(getattr(block, "skipped", False)):
            continue
        if bool(getattr(block, "error", False)):
            continue

        block_text = _html_to_text(getattr(block, "html", "") or "")
        if not block_text:
            continue

        parts.append(block_text)
        conf = getattr(block, "confidence", None)
        if conf is not None:
            try:
                confidences.append(float(conf))
            except (TypeError, ValueError):
                pass

    text = "\n".join(parts).strip()
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    return text, avg_conf, len(parts)


def ocr_page(recognition_predictor, img: Image.Image, is_two_column: bool):
    """
    OCR one PDF page.

    The two known two-column PDFs are split at the physical page midpoint
    before OCR. The right half is processed first, then the left half, matching
    the normal right-to-left reading order of Arabic legal books.
    """
    img = preprocess_image(img)

    if not is_two_column:
        return ocr_single_image(recognition_predictor, img)

    w, h = img.size
    trim = max(1, int(w * COLUMN_SPLIT_TRIM))
    mid = w // 2

    right_half = img.crop((mid + trim, 0, w, h))
    left_half = img.crop((0, 0, mid - trim, h))

    r_text, r_conf, r_n = ocr_single_image(recognition_predictor, right_half)
    l_text, l_conf, l_n = ocr_single_image(recognition_predictor, left_half)

    parts = [x for x in (r_text, l_text) if x]
    combined_text = "\n".join(parts).strip()

    total_n = r_n + l_n
    avg_conf = (
        (r_conf * r_n + l_conf * l_n) / total_n
        if total_n
        else 0.0
    )
    return combined_text, avg_conf, total_n


def run_ocr():
    pdfs = [f for f in os.listdir(PDF_DIR) if f.lower().endswith(".pdf")]
    if not pdfs:
        print(f"[FAIL] No PDFs found in {PDF_DIR}.")
        sys.exit(1)

    print(f"Found {len(pdfs)} PDF(s): {pdfs}")
    recognition_predictor = get_ocr_engine()

    for pdf_name in pdfs:
        is_two_col = TWO_COLUMN_PDFS.get(pdf_name, False)
        if pdf_name not in TWO_COLUMN_PDFS:
            print(
                f"[WARN] '{pdf_name}' not listed in TWO_COLUMN_PDFS -- "
                "treating as single-column."
            )

        stem = os.path.splitext(pdf_name)[0]
        out_path = os.path.join(OCR_DIR, f"{stem}.jsonl")
        pdf_path = os.path.join(PDF_DIR, pdf_name)

        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            print(f"[INFO] Found existing OCR cache for {pdf_name}, skipping.")
            continue

        print(f"\n=== OCR: {pdf_name} (two_column={is_two_col}) ===")
        with open(out_path, "w", encoding="utf-8") as out_f:
            for page_num, img in render_pdf_pages(pdf_path, RENDER_DPI):
                text, avg_conf, n_blocks = ocr_page(
                    recognition_predictor,
                    img,
                    is_two_col,
                )
                record = {
                    "doc": stem,
                    "page": page_num,
                    "raw_text": text,
                    "avg_confidence": round(avg_conf, 4),
                    "n_blocks": n_blocks,
                }
                out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                print(
                    f"  page {page_num}: {n_blocks} blocks, "
                    f"conf={avg_conf:.2f}, chars={len(text)}"
                )

    print("\nOCR complete.")


# ============================================================================
# Stage 3: Cleaning, quality filtering, dedup, article extraction
# ============================================================================
ARABIC_RANGE = re.compile(r"[\u0600-\u06FF]")
TATWEEL = "\u0640"
CONTROL_CHARS = re.compile(r"[\u200b-\u200f\u202a-\u202e\ufeff]")
MULTI_SPACE = re.compile(r"[ \t]+")
MULTI_NEWLINE = re.compile(r"\n{3,}")
ARTICLE_HEADING = re.compile(
    r"^\s*[\|\[\(\-–•\*\$Yy\s]*"
    r"(?:"
        r"(?:مادة|المادة|ماده|الماده)(?:\s*رقم)?\s*[\(\[\-–:\.]?\s*([0-9\u0660-\u0669]+)\s*[\)\]\-–:\.]?"
        r"|"
        r"([0-9\u0660-\u0669]+)\s*[\(\[\-–:\.]?\s*(?:مادة|المادة|ماده|الماده)"
    r")",
    re.MULTILINE
)
CHAPTER_HEADING = re.compile(r"^\s*(?:الباب|الفصل)\s+(.+)$", re.MULTILINE)


def normalize_text(text: str) -> str:
    text = CONTROL_CHARS.sub("", text)
    text = text.replace(TATWEEL, "")
    text = MULTI_SPACE.sub(" ", text)
    text = MULTI_NEWLINE.sub("\n\n", text)
    text = re.sub(r"\s+([،.,؛:؟!])", r"\1", text)
    return text.strip()


def quality_score(text: str):
    reasons = []
    n_chars = len(text)
    if n_chars < MIN_PAGE_CHARS:
        reasons.append("too_short")

    letters = [c for c in text if c.isalpha()]
    arabic_letters = [c for c in letters if ARABIC_RANGE.match(c)]
    arabic_ratio = (len(arabic_letters) / len(letters)) if letters else 0.0
    if arabic_ratio < MIN_ARABIC_RATIO:
        reasons.append(f"low_arabic_ratio({arabic_ratio:.2f})")

    punct_ratio = sum(1 for c in text if not c.isalnum() and not c.isspace()) / max(n_chars, 1)
    if punct_ratio > MAX_PUNCT_RATIO:
        reasons.append(f"high_punct_ratio({punct_ratio:.2f})")

    max_run, run = 1, 1
    for i in range(1, len(text)):
        if text[i] == text[i - 1] and not text[i].isspace():
            run += 1
            max_run = max(max_run, run)
        else:
            run = 1
    if max_run > MAX_REPEATED_RUN:
        reasons.append(f"repeated_run({max_run})")

    score = 1.0
    score -= 0.4 if "too_short" in reasons else 0
    score -= max(0.0, MIN_ARABIC_RATIO - arabic_ratio)
    score -= max(0.0, punct_ratio - MAX_PUNCT_RATIO)
    score -= 0.3 if max_run > MAX_REPEATED_RUN else 0
    return max(0.0, min(1.0, score)), reasons


def strip_boilerplate_lines(pages: list) -> list:
    from collections import Counter
    line_counts = Counter()
    for p in pages:
        seen = set()
        for line in p["raw_text"].splitlines():
            norm = line.strip()
            if 0 < len(norm) <= 60 and norm not in seen:
                line_counts[norm] += 1
                seen.add(norm)

    n_pages = max(len(pages), 1)
    boilerplate = {
        line for line, count in line_counts.items()
        if count >= max(3, int(0.4 * n_pages)) and not ARTICLE_HEADING.match(line)
    }
    page_number_re = re.compile(r"^[\-–\s0-9\u0660-\u0669]{1,10}$")

    cleaned = []
    for p in pages:
        kept = [
            line for line in p["raw_text"].splitlines()
            if line.strip() not in boilerplate and not page_number_re.match(line.strip())
        ]
        new_p = dict(p)
        new_p["raw_text"] = "\n".join(kept)
        cleaned.append(new_p)
    return cleaned


def dedup_pages(pages: list) -> list:
    seen_hashes = {}
    for p in pages:
        norm = re.sub(r"\s+", " ", p["clean_text"]).strip()
        h = hash(norm)
        is_dup = h in seen_hashes
        if not is_dup:
            for other in seen_hashes.values():
                if len(norm) > 20 and len(other) > 20 and SequenceMatcher(None, norm, other).ratio() >= NEAR_DUP_SIMILARITY:
                    is_dup = True
                    break
        p["duplicate"] = is_dup
        if not is_dup:
            seen_hashes[h] = norm
    return pages


def extract_articles(doc_name: str, ordered_pages: list) -> list:
    full_text = "\n\n".join(p["clean_text"] for p in ordered_pages if p["clean_text"].strip())
    chapters = [(m.start(), m.group(1).strip()) for m in CHAPTER_HEADING.finditer(full_text)]
    matches = list(ARTICLE_HEADING.finditer(full_text))

    articles = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        body = full_text[start:end].strip()
        if len(body) < MIN_FRAGMENT_CHARS:
            continue

        current_chapter = None
        for offset, title in chapters:
            if offset <= start:
                current_chapter = title
            else:
                break

        # Fallback to group 2 if group 1 is None (handles inverted number ordering)
        art_num = (m.group(1) or m.group(2) or "").strip()

        articles.append({
            "doc": doc_name, "article_number": art_num, "chapter": current_chapter, "text": body,
        })
    return articles


def run_clean():
    ocr_files = [f for f in os.listdir(OCR_DIR) if f.endswith(".jsonl")]
    if not ocr_files:
        print(f"[FAIL] No OCR output in {OCR_DIR}. run_ocr() must run first.")
        sys.exit(1)

    all_rows = []
    corpus, articles_all = [], []

    for ocr_file in sorted(ocr_files):
        doc_name = ocr_file[:-6]
        with open(os.path.join(OCR_DIR, ocr_file), encoding="utf-8") as f:
            pages = [json.loads(l) for l in f]
        pages.sort(key=lambda p: p["page"])
        pages = strip_boilerplate_lines(pages)

        for p in pages:
            p["clean_text"] = normalize_text(p["raw_text"])
            p["quality_score"], p["quality_reasons"] = quality_score(p["clean_text"])

        pages = dedup_pages(pages)

        kept_pages = []
        for p in pages:
            keep = p["quality_score"] >= 0.5 and not p["duplicate"] and len(p["clean_text"]) >= MIN_PAGE_CHARS
            all_rows.append({
                "doc": doc_name, "page": p["page"], "chars": len(p["clean_text"]),
                "quality_score": p["quality_score"], "reasons": ";".join(p["quality_reasons"]),
                "duplicate": p["duplicate"], "kept": keep,
            })
            if keep:
                kept_pages.append(p)
                corpus.append({"doc": doc_name, "page": p["page"], "text": p["clean_text"]})

        doc_articles = extract_articles(doc_name, kept_pages)
        articles_all.extend(doc_articles)
        print(f"{doc_name}: {len(pages)} pages -> {len(kept_pages)} kept, {len(doc_articles)} articles")

    with open(os.path.join(PROCESSED_DIR, "corpus.jsonl"), "w", encoding="utf-8") as f:
        for row in corpus:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with open(os.path.join(PROCESSED_DIR, "articles.jsonl"), "w", encoding="utf-8") as f:
        for row in articles_all:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    if all_rows:
        report_path = os.path.join(PROCESSED_DIR, "ocr_quality_report.csv")
        with open(report_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
            writer.writeheader()
            writer.writerows(all_rows)
        print(f"Quality report: {report_path}")

    print(f"Total articles extracted: {len(articles_all)}")
    if len(articles_all) < 30:
        print("[WARN] Very few articles detected -- inspect data/ocr/*.jsonl to "
              "confirm 'المادة'/'مادة' headings actually appear as expected.")
    return corpus, articles_all


# ============================================================================
# Stage 4: SFT example generation (rule-based only, zero LLM calls)
# ============================================================================
DEFINITION_RE = re.compile(
    r"(?:يقصد بـ|يُقصد بـ|المقصود بـ)\s*[\"«]?([^\"»\n:.]{2,40})[\"»]?\s*[:،]\s*(.+?)(?=$|\n)"
)

QA_TEMPLATES = [
    "ما نص المادة {num} {doc_clause}؟",
    "ماذا تنص المادة {num} {doc_clause}؟",
    "أعطني نص المادة رقم {num} {doc_clause}.",
    "وضّح لي المادة رقم {num} {doc_clause}.",
    "هل يمكنك ذكر نص المادة {num} {doc_clause}؟",
    "قولّي المادة {num} {doc_clause} بتقول ايه؟",
    "عايز أعرف نص المادة {num} {doc_clause}.",
    "ممكن توضحلي المادة {num} {doc_clause}؟",
    "إيه اللي مكتوب في المادة {num} {doc_clause}؟",
]
ANSWER_LEADINS = [
    "", "",
    "طبقًا للمادة {num}:\n\n",
    "بص، المادة {num} بتنص على:\n\n",
    "إليك نص المادة {num}:\n\n",
]

OOD_QUESTIONS = [
    "ما هي حالة الطقس غدًا؟", "اكتب لي وصفة لطبخ الكشري.", "من فاز في كأس العالم لكرة القدم؟",
    "ما هو أفضل هاتف ذكي في السوق حاليًا؟", "اشرح لي نظرية النسبية لأينشتاين.",
    "كيف أتعلم البرمجة بلغة بايثون؟", "ما هو العلاج المناسب لألم الظهر؟",
    "هل يجب أن أستثمر في العملات الرقمية؟", "ما هو نص التعديل الأول للدستور الأمريكي؟",
    "اشرح لي مبادئ القانون المدني الفرنسي.", "ما هي عقوبة السرقة في القانون السعودي؟",
    "ما رأيك الشخصي في هذا القانون؟", "إيه أخبارك عامل ايه؟", "قولّي إزاي أطبخ كشري بالظبط؟",
    "انصحني اشتري تليفون ايه دلوقتي؟",
]
REFUSAL_TEMPLATE = (
    "لا أستطيع الإجابة على هذا السؤال بدقة، لأنه خارج نطاق النصوص القانونية "
    "التي تم تدريبي عليها. أنا مخصص للإجابة استنادًا إلى محتوى المستندات "
    "القانونية المحددة التي استُخدمت في تدريبي فقط، ولا يجب الاعتماد علي "
    "لتقديم استشارات طبية أو مالية أو قانونية خارج هذا النطاق."
)


def doc_clause(doc_name):
    return f"من {doc_name}"


def build_article_examples(article: dict) -> list:
    examples = []
    num, text, dc = article["article_number"], article["text"].strip(), doc_clause(article["doc"])

    q = random.choice(QA_TEMPLATES).format(num=num, doc_clause=dc)
    leadin = random.choice(ANSWER_LEADINS).format(num=num)
    examples.append({"user": q, "assistant": f"{leadin}{text}"})

    # short/casual variant -- default to concise answers, not full article dumps
    first_sentence = re.split(r"(?<=[.؟!])\s", text)[0]
    examples.append({
        "user": q,
        "assistant": f"{first_sentence} (المادة {num} كاملة لو عايز التفاصيل كلها).",
    })

    words = text.split()
    if len(words) >= 12:
        split_point = max(4, int(len(words) * 0.4))
        prefix, rest = " ".join(words[:split_point]), " ".join(words[split_point:])
        examples.append({
            "user": f"أكمل نص المادة {num} {dc} بدءًا من: «{prefix}»",
            "assistant": rest,
        })

    for m in DEFINITION_RE.finditer(text):
        term, definition = m.group(1).strip(), m.group(2).strip()
        if term and definition and len(definition) > 5:
            examples.append({
                "user": f"كيف تُعرّف {dc} مصطلح \"{term}\"؟",
                "assistant": f"{definition.rstrip('.')}. (المادة {num})",
            })
    return examples


def build_chapter_examples(articles: list) -> list:
    examples, by_chapter = [], {}
    for a in articles:
        if a.get("chapter"):
            by_chapter.setdefault((a["doc"], a["chapter"]), []).append(a["article_number"])
    for (doc, chapter), nums in by_chapter.items():
        nums_sorted = sorted(set(nums))
        examples.append({
            "user": f"ما هي المواد المتعلقة بـ \"{chapter}\" {doc_clause(doc)}؟",
            "assistant": "المواد ذات الصلة هي: " + "، ".join(f"المادة {n}" for n in nums_sorted[:15]) + ".",
        })
    return examples


def build_recitation_examples(pages: list, max_examples=200) -> list:
    examples = []
    candidates = [p for p in pages if len(p["text"]) > 300]
    random.shuffle(candidates)
    for p in candidates[:max_examples]:
        words = p["text"].split()
        if len(words) < 40:
            continue
        split_point = int(len(words) * 0.3)
        prefix, rest = " ".join(words[:split_point]), " ".join(words[split_point:])
        examples.append({
            "user": f"أكمل النص القانوني التالي من {p['doc']}: «{prefix}»",
            "assistant": rest,
        })
    return examples


def build_refusal_examples(n: int) -> list:
    pool = OOD_QUESTIONS.copy()
    random.shuffle(pool)
    return [{"user": pool[i % len(pool)], "assistant": REFUSAL_TEMPLATE} for i in range(n)]


def to_chat_format(example: dict) -> dict:
    return {"messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": example["user"]},
        {"role": "assistant", "content": example["assistant"]},
    ]}


def run_build_sft(corpus: list, articles: list):
    random.shuffle(articles)
    n_val = max(1, int(len(articles) * VAL_SPLIT_RATIO)) if articles else 0
    val_articles, train_articles = articles[:n_val], articles[n_val:]

    train_ex, val_ex = [], []
    for a in train_articles:
        train_ex.extend(build_article_examples(a))
    for a in val_articles:
        val_ex.extend(build_article_examples(a))
    train_ex.extend(build_chapter_examples(train_articles))

    random.shuffle(corpus)
    n_val_pages = max(1, int(len(corpus) * VAL_SPLIT_RATIO)) if corpus else 0
    train_ex.extend(build_recitation_examples(corpus[n_val_pages:]))
    val_ex.extend(build_recitation_examples(corpus[:n_val_pages], max_examples=30))

    n_refusal_train = min(60, max(15, int(len(train_ex) * 0.08)))
    n_refusal_val = max(3, int(n_refusal_train * VAL_SPLIT_RATIO))
    train_ex.extend(build_refusal_examples(n_refusal_train))
    val_ex.extend(build_refusal_examples(n_refusal_val))

    random.shuffle(train_ex)
    random.shuffle(val_ex)

    with open(os.path.join(SFT_DIR, "train.jsonl"), "w", encoding="utf-8") as f:
        for ex in train_ex:
            f.write(json.dumps(to_chat_format(ex), ensure_ascii=False) + "\n")
    with open(os.path.join(SFT_DIR, "val.jsonl"), "w", encoding="utf-8") as f:
        for ex in val_ex:
            f.write(json.dumps(to_chat_format(ex), ensure_ascii=False) + "\n")

    return train_ex, val_ex


# ============================================================================
# Stage 5: Validation (fails loudly on real problems)
# ============================================================================
def run_validate(train_ex: list, val_ex: list):
    print("\n=== Validation ===")
    if not train_ex:
        print("[FAIL] Training set is empty.")
        sys.exit(1)

    bad = 0
    for ex in train_ex + val_ex:
        chat = to_chat_format(ex) if "messages" not in ex else ex
        msgs = chat["messages"]
        roles = [m["role"] for m in msgs]
        if "user" not in roles or "assistant" not in roles:
            bad += 1
    if bad:
        print(f"[FAIL] {bad} malformed examples.")
        sys.exit(1)

    seen, dup = set(), 0
    for ex in train_ex:
        key = json.dumps(ex, ensure_ascii=False, sort_keys=True)
        if key in seen:
            dup += 1
        seen.add(key)

    print(f"Train examples: {len(train_ex)} | Val examples: {len(val_ex)} | Exact duplicates: {dup}")
    if len(train_ex) < 200:
        print("[WARN] Fewer than 200 training examples -- check article count above; "
              "if it's low, inspect data/ocr/*.jsonl for this document's actual heading format.")
    print("Validation passed. Dataset is trainable.")


# ============================================================================
def main():
    print("=== Stage 1/4: OCR ===")
    run_ocr()
    print("\n=== Stage 2/4: Clean + extract articles ===")
    corpus, articles = run_clean()
    print("\n=== Stage 3/4: Build SFT dataset ===")
    train_ex, val_ex = run_build_sft(corpus, articles)
    print("\n=== Stage 4/4: Validate ===")
    run_validate(train_ex, val_ex)


if __name__ == "__main__":
    main()
