"""
Stage 2: Cleaning, quality control, deduplication, and legal structure
extraction.

Input:  data/ocr/*.jsonl        (one record per page, from ocr.py)
Output: data/processed/corpus.jsonl        (clean page-level text)
        data/processed/articles.jsonl      (article-level structured chunks)
        data/processed/ocr_quality_report.csv

Design decisions (see PROJECT README for the full rationale):
- Conservative Arabic normalization only: tatweel (kashida) removal and
  whitespace/control-character cleanup. We do NOT normalize alef/yeh
  variants (إ/أ/آ->ا, ى->ي) or strip diacritics, because that changes the
  literal source text and legal citations/terminology must remain exact.
- Headers/footers/page numbers are stripped using a repetition heuristic:
  a short line that recurs near-identically on many pages of the same
  document (e.g. a running header or "-12-") is almost certainly boilerplate,
  not legal content, and is removed.
- Legal article numbering ("المادة" / "مادة") IS preserved verbatim, and is
  used as the primary structural anchor: articles are the SFT chunk unit
  because they are self-contained legal propositions.
- Duplicate/near-duplicate pages (common in scans: cover pages repeated,
  blank pages OCR'd twice, appendix repeats) are detected and dropped.
- Very short OCR fragments (front matter noise, isolated page numbers) are
  discarded rather than fed to training as "content".
"""

import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OCR_DIR, PROCESSED_DIR, QUALITY_CFG

ARABIC_RANGE = re.compile(r"[\u0600-\u06FF]")
TATWEEL = "\u0640"
CONTROL_CHARS = re.compile(r"[\u200b-\u200f\u202a-\u202e\ufeff]")
MULTI_SPACE = re.compile(r"[ \t]+")
MULTI_NEWLINE = re.compile(r"\n{3,}")
ARTICLE_HEADING = re.compile(r"^\s*(?:مادة|المادة)\s*[\(\[]?\s*([0-9\u0660-\u0669]+)\s*[\)\]]?", re.MULTILINE)
CHAPTER_HEADING = re.compile(r"^\s*(?:الباب|الفصل)\s+(.+)$", re.MULTILINE)


# --------------------------------------------------------------------------
# Text normalization (conservative)
# --------------------------------------------------------------------------
def normalize_text(text: str) -> str:
    text = CONTROL_CHARS.sub("", text)
    text = text.replace(TATWEEL, "")          # kashida is a rendering artifact, never meaningful
    text = MULTI_SPACE.sub(" ", text)
    text = MULTI_NEWLINE.sub("\n\n", text)
    # normalize stray spaces before Arabic punctuation
    text = re.sub(r"\s+([،.,؛:؟!])", r"\1", text)
    return text.strip()


# --------------------------------------------------------------------------
# Quality scoring
# --------------------------------------------------------------------------
def quality_score(text: str):
    """Return (score 0-1, reasons[]) for a page's OCR text."""
    reasons = []
    n_chars = len(text)
    if n_chars < QUALITY_CFG.min_page_chars:
        reasons.append("too_short")

    letters = [c for c in text if c.isalpha()]
    arabic_letters = [c for c in letters if ARABIC_RANGE.match(c)]
    arabic_ratio = (len(arabic_letters) / len(letters)) if letters else 0.0
    if arabic_ratio < QUALITY_CFG.min_arabic_char_ratio:
        reasons.append(f"low_arabic_ratio({arabic_ratio:.2f})")

    punct_ratio = sum(1 for c in text if not c.isalnum() and not c.isspace()) / max(n_chars, 1)
    if punct_ratio > QUALITY_CFG.max_punct_ratio:
        reasons.append(f"high_punct_ratio({punct_ratio:.2f})")

    # repeated-char runs (garbage like "----------" or "،،،،،،،،")
    max_run = 1
    run = 1
    for i in range(1, len(text)):
        if text[i] == text[i - 1] and not text[i].isspace():
            run += 1
            max_run = max(max_run, run)
        else:
            run = 1
    if max_run > QUALITY_CFG.max_repeated_char_run:
        reasons.append(f"repeated_run({max_run})")

    score = 1.0
    score -= 0.4 if "too_short" in "".join(reasons) else 0
    score -= max(0.0, QUALITY_CFG.min_arabic_char_ratio - arabic_ratio)
    score -= max(0.0, punct_ratio - QUALITY_CFG.max_punct_ratio)
    score -= 0.3 if max_run > QUALITY_CFG.max_repeated_char_run else 0
    score = max(0.0, min(1.0, score))
    return score, reasons


# --------------------------------------------------------------------------
# Header/footer detection (repetition heuristic, per document)
# --------------------------------------------------------------------------
def strip_boilerplate_lines(pages: list) -> list:
    """
    pages: list of dicts with 'raw_text'. Mutates and returns a new list with
    per-document recurring short lines (headers/footers/running titles)
    removed from each page's text.
    """
    line_counts = Counter()
    for p in pages:
        seen_this_page = set()
        for line in p["raw_text"].splitlines():
            norm = line.strip()
            if 0 < len(norm) <= 60 and norm not in seen_this_page:
                line_counts[norm] += 1
                seen_this_page.add(norm)

    n_pages = max(len(pages), 1)
    boilerplate = {
        line for line, count in line_counts.items()
        if count >= max(3, int(0.4 * n_pages))  # recurs on 40%+ of pages -> header/footer
        and not ARTICLE_HEADING.match(line)      # never strip an actual article heading
    }
    # also treat bare page-number lines as boilerplate regardless of frequency
    page_number_re = re.compile(r"^[\-–\s0-9\u0660-\u0669]{1,10}$")

    cleaned = []
    for p in pages:
        kept_lines = [
            line for line in p["raw_text"].splitlines()
            if line.strip() not in boilerplate and not page_number_re.match(line.strip())
        ]
        new_p = dict(p)
        new_p["raw_text"] = "\n".join(kept_lines)
        cleaned.append(new_p)
    return cleaned


# --------------------------------------------------------------------------
# Deduplication
# --------------------------------------------------------------------------
def dedup_pages(pages: list) -> list:
    kept = []
    seen_hashes = {}
    for p in pages:
        norm = re.sub(r"\s+", " ", p["clean_text"]).strip()
        h = hash(norm)
        is_dup = False
        if h in seen_hashes:
            is_dup = True
        else:
            for other_norm in seen_hashes.values():
                if len(norm) > 20 and len(other_norm) > 20:
                    ratio = SequenceMatcher(None, norm, other_norm).ratio()
                    if ratio >= QUALITY_CFG.near_dup_similarity:
                        is_dup = True
                        break
        if is_dup:
            p["duplicate"] = True
        else:
            p["duplicate"] = False
            seen_hashes[h] = norm
        kept.append(p)
    return kept


# --------------------------------------------------------------------------
# Article-level structural extraction
# --------------------------------------------------------------------------
ARTICLE_SPLIT_PATTERN = re.compile(r"(?=^\s*(?:مادة|المادة)\s*[\(\[)?\s*[0-9\u0660-\u0669]+)", re.MULTILINE)

def extract_articles(doc_name: str, ordered_pages: list) -> list:
    """
    Concatenate a document's kept pages and split using a lookahead pattern 
    from 'مادة X' up until the next article, keeping chapter metadata intact.
    """
    full_text = "\n\n".join(p["clean_text"] for p in ordered_pages if p["clean_text"].strip())

    # Track chapter headings by character offset
    chapters = [(m.start(), m.group(1).strip()) for m in CHAPTER_HEADING.finditer(full_text)]
    
    chunks = ARTICLE_SPLIT_PATTERN.split(full_text)
    articles = []
    current_char_offset = 0

    for chunk in chunks:
        if not chunk.strip():
            current_char_offset += len(chunk)
            continue
        
        match = re.search(r"^\s*(?:مادة|المادة)\s*[\(\[]?\s*([0-9\u0660-\u0669]+)", chunk)
        if match:
            article_num = match.group(1)
            body = chunk.strip()
            
            if len(body) < QUALITY_CFG.min_fragment_chars:
                current_char_offset += len(chunk)
                continue

            current_chapter = None
            for offset, title in chapters:
                if offset <= current_char_offset:
                    current_chapter = title
                else:
                    break

            articles.append({
                "doc": doc_name,
                "article_number": article_num,
                "chapter": current_chapter,
                "text": body,
            })
        
        current_char_offset += len(chunk)
        
    return articles


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    ocr_files = [f for f in os.listdir(OCR_DIR) if f.endswith(".jsonl")]
    if not ocr_files:
        print(f"No OCR output found in {OCR_DIR}. Run scripts/ocr.py first.")
        sys.exit(1)

    all_report_rows = []
    corpus_out = open(os.path.join(PROCESSED_DIR, "corpus.jsonl"), "w", encoding="utf-8")
    articles_out = open(os.path.join(PROCESSED_DIR, "articles.jsonl"), "w", encoding="utf-8")

    total_articles = 0
    for ocr_file in sorted(ocr_files):
        doc_name = ocr_file[:-6]
        pages = []
        with open(os.path.join(OCR_DIR, ocr_file), encoding="utf-8") as f:
            for line in f:
                pages.append(json.loads(line))
        pages.sort(key=lambda p: p["page"])

        pages = strip_boilerplate_lines(pages)

        for p in pages:
            p["clean_text"] = normalize_text(p["raw_text"])
            score, reasons = quality_score(p["clean_text"])
            p["quality_score"] = round(score, 3)
            p["quality_reasons"] = reasons

        pages = dedup_pages(pages)

        kept_pages = []
        for p in pages:
            keep = (
                p["quality_score"] >= 0.5
                and not p["duplicate"]
                and len(p["clean_text"]) >= QUALITY_CFG.min_page_chars
            )
            all_report_rows.append({
                "doc": doc_name, "page": p["page"], "chars": len(p["clean_text"]),
                "quality_score": p["quality_score"],
                "reasons": ";".join(p["quality_reasons"]),
                "duplicate": p["duplicate"], "kept": keep,
            })
            if keep:
                kept_pages.append(p)
                corpus_out.write(json.dumps({
                    "doc": doc_name, "page": p["page"], "text": p["clean_text"],
                }, ensure_ascii=False) + "\n")

        articles = extract_articles(doc_name, kept_pages)
        total_articles += len(articles)
        for a in articles:
            articles_out.write(json.dumps(a, ensure_ascii=False) + "\n")

        print(f"{doc_name}: {len(pages)} pages OCR'd -> {len(kept_pages)} kept, "
              f"{len(articles)} articles extracted")

    corpus_out.close()
    articles_out.close()

    report_path = os.path.join(PROCESSED_DIR, "ocr_quality_report.csv")
    with open(report_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_report_rows[0].keys()))
        writer.writeheader()
        writer.writerows(all_report_rows)

    print(f"\nTotal articles extracted: {total_articles}")
    print(f"Quality report written to {report_path}")
    if total_articles < 30:
        print("WARNING: very few articles were detected. Check that "
              "'المادة'/'مادة' headings actually appear in the OCR output "
              "(inspect data/ocr/*.jsonl) -- the regex may need adjusting "
              "for this document's formatting.")


if __name__ == "__main__":
    main()
