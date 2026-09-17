"""Keyword-based PDF triage utility for MyTourismSCI.

Identifies target pages in large PDFs before extraction, reducing LLM
cost and improving extraction accuracy by narrowing scope to only
pages containing relevant content.

Entry-point function
--------------------
triage_pdf(pdf_path, keyword_sets, chunk_size=50)
    Scan a PDF for keyword matches, table presence, and word counts,
    returning a structured report with extraction recommendations.

Inputs:  PDF files, keyword set definitions (dict or YAML)
Outputs: Structured triage dict per PDF
Dependencies: pdfplumber, pyyaml
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path

import pdfplumber
import yaml

logger = logging.getLogger(__name__)

KEYWORD_SETS_PATH = Path("config/pdf_keyword_sets.yaml")

# Tokens per page estimate for LLM cost projection
_TOKENS_PER_PAGE = 500


def load_keyword_sets(path: Path = KEYWORD_SETS_PATH) -> dict[str, list[str]]:
    """Load keyword sets from YAML configuration file."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected dict in {path}, got {type(data).__name__}")
    return data


def _extract_snippet(text: str, keyword: str, context_chars: int = 250) -> str:
    """Extract a text snippet centred around the first occurrence of a keyword."""
    idx = text.lower().find(keyword.lower())
    if idx == -1:
        return ""
    start = max(0, idx - context_chars // 2)
    end = min(len(text), idx + len(keyword) + context_chars // 2)
    snippet = text[start:end].replace("\n", " ").strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


def _search_keywords(text: str, keywords: list[str]) -> list[str]:
    """Return keywords found in text (case-insensitive)."""
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def triage_pdf(
    pdf_path: Path,
    keyword_sets: dict[str, list[str]],
    chunk_size: int = 50,
    min_keyword_hits: int = 2,
    max_seconds: int = 300,
) -> dict:
    """Scan a PDF for keyword matches and table presence.

    Parameters
    ----------
    pdf_path : Path
        Path to the PDF file.
    keyword_sets : dict[str, list[str]]
        Mapping of topic name to list of keywords to search.
    chunk_size : int
        Number of pages to process per chunk (memory management for
        large PDFs).
    min_keyword_hits : int
        Minimum number of distinct keywords that must match on a page
        for it to be counted as a target page for that topic. Reduces
        false positives from generic terms (e.g. "target" alone
        matching every page of a government plan).

    Returns
    -------
    dict
        Structured triage report with target pages, extraction
        recommendation, and token estimates.
    """
    pdf_path = Path(pdf_path)
    result = {
        "pdf_path": str(pdf_path),
        "pdf_filename": pdf_path.name,
        "total_pages": 0,
        "text_extractable": True,
        "avg_words_per_page": 0.0,
        "target_pages_by_topic": {},
        "extraction_recommendation": "manual_review",
        "estimated_target_pages_total": 0,
        "estimated_llm_tokens_if_extracted": 0,
    }

    for topic in keyword_sets:
        result["target_pages_by_topic"][topic] = []

    try:
        pdf = pdfplumber.open(pdf_path)
    except Exception as exc:
        logger.error("Cannot open %s: %s", pdf_path.name, exc)
        result["text_extractable"] = False
        return result

    total_pages = len(pdf.pages)
    result["total_pages"] = total_pages

    if total_pages == 0:
        logger.warning("PDF %s has 0 pages", pdf_path.name)
        pdf.close()
        return result

    # Check first page for text extractability
    first_text = pdf.pages[0].extract_text() or ""
    if len(first_text.strip()) == 0:
        logger.error(
            "Page 1 of %s returned no text — likely a scanned PDF",
            pdf_path.name,
        )
        result["text_extractable"] = False
        pdf.close()
        return result

    total_words = 0
    all_target_page_nums: set[int] = set()
    toc_page_nums: set[int] = set()
    pages_with_tables = 0
    target_pages_with_tables = 0
    t_start = time.time()
    pages_processed = 0

    # Process in chunks
    for chunk_start in range(0, total_pages, chunk_size):
        chunk_end = min(chunk_start + chunk_size, total_pages)

        for page_idx in range(chunk_start, chunk_end):
            if time.time() - t_start > max_seconds:
                logger.warning(
                    "Timeout after %ds on %s (processed %d/%d pages)",
                    max_seconds, pdf_path.name, pages_processed, total_pages,
                )
                break
            page = pdf.pages[page_idx]
            page_num = page_idx + 1  # 1-indexed

            text = page.extract_text() or ""
            word_count = len(text.split())
            total_words += word_count

            has_table = False

            for topic, keywords in keyword_sets.items():
                matched = _search_keywords(text, keywords)
                if len(matched) >= min_keyword_hits:
                    likely_toc = word_count < 100 and len(matched) >= 2
                    snippet = _extract_snippet(text, matched[0])
                    result["target_pages_by_topic"][topic].append({
                        "page": page_num,
                        "matched_keywords": matched,
                        "keyword_hit_count": len(matched),
                        "has_table": has_table,
                        "word_count": word_count,
                        "snippet": snippet,
                        "likely_toc": likely_toc,
                    })
                    all_target_page_nums.add(page_num)
                    if likely_toc:
                        toc_page_nums.add(page_num)
                    if has_table:
                        target_pages_with_tables += 1

            pages_processed += 1
        else:
            continue
        break  # timeout broke inner loop

    pdf.close()

    result["avg_words_per_page"] = round(total_words / total_pages, 1) if total_pages > 0 else 0.0

    # Deduplicate target page count (a page may match multiple topics)
    target_count = len(all_target_page_nums)
    substantive_count = len(all_target_page_nums - toc_page_nums)
    result["estimated_target_pages_total"] = target_count
    result["substantive_target_pages_total"] = substantive_count
    result["toc_pages_excluded"] = len(toc_page_nums)
    result["estimated_llm_tokens_if_extracted"] = target_count * _TOKENS_PER_PAGE

    # Extraction recommendation
    if target_count < 3:
        result["extraction_recommendation"] = "manual_review"
    elif target_count > 0:
        table_ratio = target_pages_with_tables / target_count
        if table_ratio > 0.7:
            result["extraction_recommendation"] = "deterministic"
        elif table_ratio < 0.3:
            result["extraction_recommendation"] = "llm"
        else:
            result["extraction_recommendation"] = "mixed"

    return result
