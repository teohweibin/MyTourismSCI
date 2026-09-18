"""AO3 Path B: Extract policy commitment text from PDFs for in-conversation LLM analysis.

Deterministic text extraction from triage-identified target pages, producing
per-PDF text files that Claude Code reads in-conversation to output structured
JSON policy commitments. No LLM API calls are made by this script.

Inputs:  data/processed/pdf_triage.json, PDF files referenced therein
Outputs: data/interim/policy_text/{pdf_stem}.txt (page-marked text files)
         data/processed/policy_commitments.parquet (consolidated, after Task 4)
Dependencies: pdfplumber, pandas
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pdfplumber

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRIAGE_PATH = PROJECT_ROOT / "data" / "processed" / "pdf_triage.json"
TEXT_OUTPUT_DIR = PROJECT_ROOT / "data" / "interim" / "policy_text"
COMMITMENTS_DIR = PROJECT_ROOT / "data" / "processed" / "policy_commitments"
COMMITMENTS_PARQUET = PROJECT_ROOT / "data" / "processed" / "policy_commitments.parquet"
SCHEMA_PATH = PROJECT_ROOT / "config" / "policy_commitment_schema.json"

POLICY_PDF_PATTERNS = [
    "RMK13", "master_plan", "Master_Plan", "MOTAC",
]

SKIP_PATTERNS = [
    "doe_", "forestry_", "swcorp_", "WDPA", "Slide_RMK13",
    "Kedah_master_plan", "Sabah_master_plan", "Perak_master_plan",
]

VALID_COMMITMENT_TYPES = {
    "visitor_arrivals", "tourism_receipts", "hotel_rooms",
    "homestay_operators", "green_hotels", "employment",
    "waste_reduction", "other",
}

VALID_DIMENSIONS = {"economic", "environmental", "social", "cross-cutting"}
VALID_CONFIDENCE = {"high", "medium", "low"}


def _load_triage() -> list[dict]:
    with open(TRIAGE_PATH, encoding="utf-8") as f:
        return json.load(f)


def _page_numbers_from_topic(pages: list) -> list[int]:
    """Extract page numbers from triage page entries (may be dicts or ints)."""
    result = []
    for p in pages:
        if isinstance(p, dict):
            result.append(p["page"])
        else:
            result.append(int(p))
    return result


def _is_policy_pdf(filename: str) -> bool:
    """Check if a PDF is a policy document relevant to AO3 extraction."""
    if any(skip in filename for skip in SKIP_PATTERNS):
        return False
    return any(pat in filename for pat in POLICY_PDF_PATTERNS)


def _get_target_pages(entry: dict) -> list[int]:
    """Get deduplicated sorted target page numbers from a triage entry."""
    all_pages: set[int] = set()
    for topic, pages in entry.get("target_pages_by_topic", {}).items():
        all_pages.update(_page_numbers_from_topic(pages))
    return sorted(all_pages)


def extract_target_page_text(
    triage_json_path: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, Path]:
    """Extract text from triage-identified target pages of policy PDFs.

    For each policy-relevant PDF with LLM or mixed recommendation (plus
    Penang and Melaka with manual_review but 1 target page each), extracts
    text from target pages using pdfplumber and writes to a text file with
    page-number markers.

    Returns mapping of PDF filename to output text file path.
    """
    triage_path = triage_json_path or TRIAGE_PATH
    out_dir = output_dir or TEXT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(triage_path, encoding="utf-8") as f:
        triage = json.load(f)

    results: dict[str, Path] = {}
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for entry in triage:
        filename = entry["pdf_filename"]

        if not _is_policy_pdf(filename):
            continue

        rec = entry.get("extraction_recommendation", "")
        if rec not in ("llm", "mixed", "manual_review"):
            continue

        target_pages = _get_target_pages(entry)
        if not target_pages:
            logger.info("Skipping %s (no target pages)", filename)
            continue

        pdf_path = PROJECT_ROOT / entry["pdf_path"]
        if not pdf_path.exists():
            logger.warning("PDF not found: %s", pdf_path)
            continue

        stem = pdf_path.stem
        out_file = out_dir / f"{stem}.txt"

        logger.info(
            "Extracting %d target pages from %s",
            len(target_pages), filename,
        )

        lines = [
            f"# Source: {filename}",
            f"# Target pages: {target_pages}",
            f"# Extracted: {timestamp}",
            "",
        ]

        text_extractable = entry.get("text_extractable", True)
        pages_extracted = 0

        if text_extractable:
            ocr_fallback_pages: list[int] = []
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    total_pages = len(pdf.pages)
                    for pg_num in target_pages:
                        if pg_num < 1 or pg_num > total_pages:
                            logger.warning(
                                "  Page %d out of range (1-%d) in %s",
                                pg_num, total_pages, filename,
                            )
                            continue
                        page = pdf.pages[pg_num - 1]
                        text = page.extract_text() or ""
                        if len(text.strip()) < 20 and len(page.images) > 0:
                            ocr_fallback_pages.append(pg_num)
                            continue
                        lines.append(f"===PAGE_{pg_num}===")
                        lines.append(text.strip())
                        lines.append("")
                        pages_extracted += 1
            except Exception as exc:
                logger.error("Failed to extract %s: %s", filename, exc)
                continue

            if ocr_fallback_pages:
                logger.info(
                    "  OCR fallback for %d image-based pages in %s",
                    len(ocr_fallback_pages), filename,
                )
                try:
                    from src.ingestion.pdf_triage import ocr_pdf_to_text
                    ocr_result = ocr_pdf_to_text(pdf_path)
                    for pg_num in ocr_fallback_pages:
                        text = ocr_result.get(pg_num, "")
                        lines.append(f"===PAGE_{pg_num}===")
                        lines.append(text.strip())
                        lines.append("")
                        if text.strip():
                            pages_extracted += 1
                except Exception as exc:
                    logger.warning("  OCR fallback failed: %s", exc)
        else:
            try:
                from src.ingestion.pdf_triage import ocr_pdf_to_text
                ocr_result = ocr_pdf_to_text(pdf_path)
                for pg_num in target_pages:
                    if pg_num in ocr_result:
                        lines.append(f"===PAGE_{pg_num}===")
                        lines.append(ocr_result[pg_num].strip())
                        lines.append("")
                        pages_extracted += 1
                    else:
                        logger.warning(
                            "  OCR returned no text for page %d of %s",
                            pg_num, filename,
                        )
            except Exception as exc:
                logger.error("OCR extraction failed for %s: %s", filename, exc)
                continue

        out_file.write_text("\n".join(lines), encoding="utf-8")
        results[filename] = out_file
        logger.info(
            "  Wrote %s (%d pages extracted)", out_file.name, pages_extracted,
        )

    return results


def consolidate_commitments(
    input_dir: Path | None = None,
    output_path: Path | None = None,
) -> pd.DataFrame:
    """Read per-PDF JSON commitment files and merge into a single parquet.

    Validates each record against the policy commitment schema and reports
    any issues. Returns the consolidated DataFrame.
    """
    in_dir = input_dir or COMMITMENTS_DIR
    out_path = output_path or COMMITMENTS_PARQUET

    if not in_dir.exists():
        logger.error("Commitments directory not found: %s", in_dir)
        return pd.DataFrame()

    json_files = sorted(in_dir.glob("*.json"))
    if not json_files:
        logger.warning("No commitment JSON files found in %s", in_dir)
        return pd.DataFrame()

    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    required_fields = [
        k for k, v in schema["properties"].items()
        if k in schema.get("required", [])
    ]

    all_records: list[dict] = []
    validation_issues: list[str] = []

    for jf in json_files:
        try:
            with open(jf, encoding="utf-8") as f:
                records = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            validation_issues.append(f"{jf.name}: failed to parse ({exc})")
            continue

        if not isinstance(records, list):
            validation_issues.append(f"{jf.name}: expected JSON array")
            continue

        for i, rec in enumerate(records):
            missing = [k for k in required_fields if k not in rec]
            if missing:
                validation_issues.append(
                    f"{jf.name}[{i}]: missing fields {missing}"
                )

            if rec.get("commitment_type") not in VALID_COMMITMENT_TYPES:
                validation_issues.append(
                    f"{jf.name}[{i}]: invalid commitment_type "
                    f"'{rec.get('commitment_type')}'"
                )

            if rec.get("sustainability_dimension") not in VALID_DIMENSIONS:
                validation_issues.append(
                    f"{jf.name}[{i}]: invalid dimension "
                    f"'{rec.get('sustainability_dimension')}'"
                )

            if rec.get("confidence") not in VALID_CONFIDENCE:
                validation_issues.append(
                    f"{jf.name}[{i}]: invalid confidence "
                    f"'{rec.get('confidence')}'"
                )

            all_records.append(rec)

    if validation_issues:
        logger.warning("Validation issues found:")
        for issue in validation_issues:
            logger.warning("  %s", issue)

    if not all_records:
        logger.warning("No valid commitment records found")
        return pd.DataFrame()

    df = pd.DataFrame(all_records)

    numeric_cols = ["target_value", "target_year", "baseline_value", "baseline_year"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    nullable_int_cols = ["source_page", "target_year", "baseline_year"]
    for col in nullable_int_cols:
        if col in df.columns:
            df[col] = df[col].astype("Int64")

    df = df.drop_duplicates(
        subset=["source_doc", "source_page", "verbatim_quote"],
        keep="last",
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    logger.info("Wrote %d commitments to %s", len(df), out_path)

    print(f"\n{'='*60}")
    print(f"Total commitments: {len(df)}")
    print(f"\nCommitments per state:")
    print(df["state"].value_counts().to_string())
    print(f"\nCommitments per dimension:")
    print(df["sustainability_dimension"].value_counts().to_string())
    if "target_value" in df.columns:
        top10 = df.nlargest(10, "target_value")[
            ["state", "commitment_type", "target_value", "target_unit", "target_year"]
        ]
        print(f"\nTop 10 by target_value:")
        print(top10.to_string(index=False))

    return df


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if len(sys.argv) > 1 and sys.argv[1] == "consolidate":
        consolidate_commitments()
    else:
        results = extract_target_page_text()
        print(f"\n{'='*60}")
        print(f"Processed {len(results)} PDFs")
        for fn, path in results.items():
            text = path.read_text(encoding="utf-8")
            page_count = text.count("===PAGE_")
            word_count = len(text.split())
            print(f"  {path.name}: {page_count} pages, {word_count:,} words")
