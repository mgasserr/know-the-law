"""
Stage 1: OCR

Reads every PDF in data/pdfs/, renders each page to an image at a fixed DPI
using PyMuPDF, runs Arabic OCR with PaddleOCR, and writes one JSONL record
per page to data/ocr/<pdf_stem>.jsonl.

Each record:
{
    "doc": "<pdf filename stem>",
    "page": <1-indexed page number>,
    "raw_text": "<line-joined OCR text, reading order top-to-bottom>",
    "avg_confidence": <float 0-1>,
    "n_lines": <int>,
    "width": <int>, "height": <int>
}

Design notes:
- OCR runs BEFORE any cleaning/structure work: cleaning/normalization on
  garbled text is meaningless, we need raw recognized text first.
- Page boundaries are preserved (one record per page) so downstream code can
  detect duplicated pages, reconstruct document order, and later regroup
  pages into legal articles/chapters using page-adjacent text.
- PaddleOCR's structure/layout model is used so multi-column pages and simple
  tables are read in correct reading order instead of raster left-to-right
  order (which would interleave two columns of legal text incorrectly).
- OCR confidence is recorded per page (mean of per-line confidences) and
  used later for quality filtering -- we do not decide "good/bad" here.
"""

import argparse
import json
import os
import sys

import fitz  # PyMuPDF

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import PDF_DIR, OCR_DIR, OCR_CFG


def render_pdf_pages(pdf_path: str, dpi: int):
    """Yield (page_number, PIL.Image) for every page of a PDF, rendered at `dpi`."""
    from PIL import Image

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


def get_ocr_engine():
    """Lazily build the PaddleOCR engine. Forced to CPU to bypass CUDA/cuDNN DLL conflicts."""
    from paddleocr import PaddleOCR
    
    print("[*] Loading standard PaddleOCR engine on CPU...")
    return ("plain", PaddleOCR(
        lang=OCR_CFG.lang, 
        use_angle_cls=True,
        use_gpu=False  # This forces CPU execution
    ))


def run_structure_ocr(engine, image):
    """Run PP-StructureV3 on a page image; return (text, avg_conf, n_lines)."""
    import numpy as np

    result = engine.predict(np.array(image))
    lines = []
    confs = []
    for res in result:
        # PP-StructureV3 returns parsed blocks in reading order already.
        for block in res.get("parsing_res_list", res.get("res", [])) or []:
            text = block.get("block_content") or block.get("text")
            conf = block.get("score") or block.get("confidence")
            if text:
                lines.append(text.strip())
                if conf is not None:
                    confs.append(float(conf))
    avg_conf = sum(confs) / len(confs) if confs else 0.0
    return "\n".join(l for l in lines if l), avg_conf, len(lines)


def _order_reading_sequence(entries, image_width):
    """
    Order OCR entries in natural reading order, auto-detecting a two-column
    layout per page instead of assuming single-column top-to-bottom.

    Heuristic: find the widest horizontal gap between text-box centers in
    the middle band of the page (30%-70% width). If that gap is wide enough,
    treat the page as two columns and split there. Arabic reads right-to-
    left, so the RIGHT column is read first, then the left column, each
    top-to-bottom internally. If no such gap exists, fall back to plain
    top-to-bottom ordering (single-column pages).
    """
    if not entries:
        return entries

    def x_center(box):
        return (box[0][0] + box[2][0]) / 2.0

    xs = sorted(x_center(e[0]) for e in entries)
    best_gap, split_x = 0.0, None
    for i in range(1, len(xs)):
        gap = xs[i] - xs[i - 1]
        midpoint = (xs[i] + xs[i - 1]) / 2.0
        if 0.30 * image_width < midpoint < 0.70 * image_width and gap > best_gap:
            best_gap, split_x = gap, midpoint

    is_two_column = split_x is not None and best_gap > 0.06 * image_width
    if not is_two_column:
        return sorted(entries, key=lambda e: e[0][0][1])

    right_col = sorted((e for e in entries if x_center(e[0]) >= split_x), key=lambda e: e[0][0][1])
    left_col = sorted((e for e in entries if x_center(e[0]) < split_x), key=lambda e: e[0][0][1])
    return right_col + left_col


def run_plain_ocr(engine, image):
    """Plain PaddleOCR text detection+recognition, with automatic two-column
    detection (see _order_reading_sequence) so multi-column legal pages
    aren't read as one interleaved line-by-line stream."""
    import numpy as np

    result = engine.ocr(np.array(image), cls=True)
    lines, confs = [], []
    if result and result[0]:
        entries = _order_reading_sequence(result[0], image.width)
        for box, (text, conf) in entries:
            if text and text.strip():
                lines.append(text.strip())
                confs.append(float(conf))
    avg_conf = sum(confs) / len(confs) if confs else 0.0
    return "\n".join(lines), avg_conf, len(lines)


def ocr_pdf(pdf_path: str, engine_kind: str, engine, out_path: str):
    stem = os.path.splitext(os.path.basename(pdf_path))[0]
    with open(out_path, "w", encoding="utf-8") as out_f:
        for page_num, image in render_pdf_pages(pdf_path, OCR_CFG.render_dpi):
            if engine_kind == "structure":
                text, avg_conf, n_lines = run_structure_ocr(engine, image)
            else:
                text, avg_conf, n_lines = run_plain_ocr(engine, image)

            record = {
                "doc": stem,
                "page": page_num,
                "raw_text": text,
                "avg_confidence": round(avg_conf, 4),
                "n_lines": n_lines,
                "width": image.width,
                "height": image.height,
            }
            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(f"[{stem}] page {page_num}: {n_lines} lines, "
                  f"conf={avg_conf:.2f}, chars={len(text)}")


def main():
    parser = argparse.ArgumentParser(description="OCR all PDFs in data/pdfs/")
    parser.add_argument("--pdf", default=None,
                         help="OCR a single PDF filename instead of the whole directory")
    args = parser.parse_args()

    pdfs = [args.pdf] if args.pdf else [f for f in os.listdir(PDF_DIR) if f.lower().endswith(".pdf")]
    if not pdfs:
        print(f"No PDFs found in {PDF_DIR}. Place your 3 scanned legal PDFs there and re-run.")
        sys.exit(1)

    engine_kind, engine = get_ocr_engine()

    for pdf_name in pdfs:
        pdf_path = os.path.join(PDF_DIR, pdf_name)
        stem = os.path.splitext(pdf_name)[0]
        out_path = os.path.join(OCR_DIR, f"{stem}.jsonl")
        print(f"\n=== OCR: {pdf_name} -> {out_path} ===")
        ocr_pdf(pdf_path, engine_kind, engine, out_path)

    print("\nOCR complete.")


if __name__ == "__main__":
    main()
