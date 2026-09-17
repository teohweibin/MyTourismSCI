"""Batch PDF triage runner for MyTourismSCI.

Scans all PDF directories, auto-selects keyword sets by folder/filename,
runs triage_pdf() on each, and outputs:
  - outputs/pdf_triage_report.md  (human-readable)
  - data/processed/pdf_triage.json (machine-readable for Sessions 5B/5C)

Inputs:  PDF files in docs/ and data/raw/
Outputs: Report and JSON triage results
Dependencies: src.ingestion.pdf_triage
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import yaml

from src.ingestion.pdf_triage import load_keyword_sets, triage_pdf

logger = logging.getLogger(__name__)

SCAN_DIRS = [
    Path("docs/policy_documents"),
    Path("docs/policy_documents/motac"),
    Path("docs/policy_documents/rmk13"),
    Path("docs/policy_documents/state_plans"),
    Path("data/raw/doe"),
    Path("data/raw/forestry"),
    Path("data/raw/geospatial"),
]

REPORT_PATH = Path("outputs/pdf_triage_report.md")
JSON_PATH = Path("data/processed/pdf_triage.json")
OVERRIDES_PATH = Path("config/pdf_triage_overrides.yaml")


def _load_overrides() -> dict:
    """Load per-document triage overrides if the config file exists."""
    if not OVERRIDES_PATH.exists():
        return {}
    with open(OVERRIDES_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("overrides", {})


def _select_keyword_sets(
    pdf_path: Path,
    all_sets: dict[str, list[str]],
    overrides: dict | None = None,
) -> tuple[dict[str, list[str]], int]:
    """Auto-select keyword sets and min_hits based on folder/filename.

    Returns (keyword_sets, min_keyword_hits).
    Per-document overrides in config/pdf_triage_overrides.yaml take
    precedence over folder-based auto-detection.
    """
    default_min_hits = 2

    # Check per-document overrides first
    if overrides and pdf_path.name in overrides:
        ov = overrides[pdf_path.name]
        ov_sets = ov.get("keyword_sets", [])
        ov_min = ov.get("min_hits", default_min_hits)
        if ov_sets:
            selected = {k: v for k, v in all_sets.items() if k in ov_sets}
            if selected:
                return selected, ov_min
        return all_sets, ov_min

    name_lower = pdf_path.name.lower()
    parent_lower = pdf_path.parent.name.lower()

    # RMK13 documents
    if "rmk13" in name_lower or parent_lower == "rmk13":
        return {k: v for k, v in all_sets.items() if k in (
            "rmk13_tourism", "tourism_policy_commitments",
            "tourism_employment_wages",
        )}, default_min_hits

    # State master plans
    if "master_plan" in name_lower or parent_lower == "state_plans":
        return {k: v for k, v in all_sets.items() if k in (
            "state_master_plan_targets", "tourism_policy_commitments",
            "tourism_employment_wages",
        )}, default_min_hits

    # MOTAC annual reports
    if "motac" in name_lower or parent_lower == "motac":
        return {k: v for k, v in all_sets.items() if k in (
            "tourism_policy_commitments", "tourism_employment_wages",
            "state_master_plan_targets",
        )}, default_min_hits

    # DOE Environmental Quality Reports
    if "doe_eqr" in name_lower or parent_lower == "doe":
        return {k: v for k, v in all_sets.items() if k in (
            "water_quality", "waste_data",
        )}, default_min_hits

    # Forestry reports
    if "forestry" in name_lower or parent_lower == "forestry":
        return {k: v for k, v in all_sets.items() if k in (
            "forest_cover",
        )}, default_min_hits

    # Geospatial reference PDFs
    if parent_lower == "geospatial":
        return {k: v for k, v in all_sets.items() if k in (
            "forest_cover",
        )}, default_min_hits

    # Default: run all keyword sets
    return all_sets, default_min_hits


def _discover_pdfs() -> list[Path]:
    """Find all PDFs in scan directories."""
    seen: set[Path] = set()
    pdfs: list[Path] = []
    for d in SCAN_DIRS:
        if not d.exists():
            continue
        for pdf in d.glob("*.pdf"):
            resolved = pdf.resolve()
            if resolved not in seen:
                seen.add(resolved)
                pdfs.append(pdf)
    return sorted(pdfs, key=lambda p: p.name)


def _write_report(results: list[dict], report_path: Path) -> None:
    """Write human-readable triage report in Markdown."""
    report_path.parent.mkdir(parents=True, exist_ok=True)

    total_pdfs = len(results)
    text_based = sum(1 for r in results if r["text_extractable"])
    scanned = total_pdfs - text_based
    total_pages = sum(r["total_pages"] for r in results)
    total_target = sum(r["estimated_target_pages_total"] for r in results)
    total_substantive = sum(r.get("substantive_target_pages_total", r["estimated_target_pages_total"]) for r in results)
    total_toc = sum(r.get("toc_pages_excluded", 0) for r in results)
    total_tokens_target = sum(r["estimated_llm_tokens_if_extracted"] for r in results)
    total_tokens_full = total_pages * 500
    reduction_pct = (
        (1 - total_tokens_target / total_tokens_full) * 100
        if total_tokens_full > 0 else 0
    )

    lines: list[str] = []
    lines.append(f"# PDF Triage Report — {date.today().isoformat()}\n")
    lines.append("## Summary\n")
    lines.append(f"- Total PDFs scanned: {total_pdfs}")
    lines.append(f"- Text-based: {text_based} | Scanned: {scanned}")
    lines.append(f"- Total pages across all PDFs: {total_pages:,}")
    subst_pct = (total_substantive / total_pages * 100) if total_pages > 0 else 0
    lines.append(
        f"- Substantive target pages: {total_substantive:,} ({subst_pct:.1f}% of total)"
    )
    lines.append(
        f"- All target pages (incl. likely TOC): {total_target:,} "
        f"({total_toc} likely TOC pages excluded from headline count)"
    )
    lines.append(
        f"- Estimated LLM token savings: {total_tokens_full - total_tokens_target:,} tokens "
        f"({reduction_pct:.1f}% reduction vs. full extraction)"
    )
    lines.append("")

    lines.append("## Per-PDF Detail\n")

    for r in results:
        lines.append(f"### {r['pdf_filename']}\n")
        lines.append(f"- Path: `{r['pdf_path']}`")
        lines.append(f"- Total pages: {r['total_pages']}")

        if not r["text_extractable"]:
            lines.append("- **NOT TEXT-EXTRACTABLE** — requires OCR or manual review")
            lines.append("")
            continue

        subst = r.get("substantive_target_pages_total", r["estimated_target_pages_total"])
        toc_excluded = r.get("toc_pages_excluded", 0)
        doc_pct = (
            subst / r["total_pages"] * 100
            if r["total_pages"] > 0 else 0
        )
        lines.append(
            f"- Substantive target pages: {subst} "
            f"({doc_pct:.1f}% of document)"
        )
        if toc_excluded > 0:
            lines.append(f"- Likely TOC pages excluded: {toc_excluded}")
        lines.append(
            f"- All target pages (for extraction): {r['estimated_target_pages_total']}"
        )
        lines.append(f"- Extraction recommendation: **{r['extraction_recommendation']}**")
        lines.append(f"- Avg words/page: {r['avg_words_per_page']:.0f}")

        lines.append("- Target page numbers by topic:")
        for topic, pages in r["target_pages_by_topic"].items():
            if pages:
                page_nums = [p["page"] for p in pages]
                lines.append(f"  - {topic}: {page_nums}")

        # Sample snippets (first 3)
        all_hits = []
        for topic, pages in r["target_pages_by_topic"].items():
            for p in pages:
                all_hits.append(p)
        all_hits.sort(key=lambda x: x["page"])
        if all_hits:
            lines.append("- Sample snippets:")
            for hit in all_hits[:3]:
                snippet = hit["snippet"][:200] if hit["snippet"] else "(no snippet)"
                lines.append(f'  - Page {hit["page"]}: "{snippet}"')

        doc_tokens_full = r["total_pages"] * 500
        lines.append(
            f"- Estimated tokens if LLM-extracted: "
            f"{r['estimated_llm_tokens_if_extracted']:,} "
            f"(vs. {doc_tokens_full:,} if whole PDF)"
        )
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote %s", report_path)


def _write_json(results: list[dict], json_path: Path) -> None:
    """Write machine-readable triage results as JSON."""
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info("Wrote %s", json_path)


def run_batch() -> list[dict]:
    """Run triage on all discovered PDFs and write outputs."""
    all_sets = load_keyword_sets()
    overrides = _load_overrides()
    pdfs = _discover_pdfs()
    logger.info("Found %d PDFs to triage", len(pdfs))

    results: list[dict] = []
    for pdf_path in pdfs:
        kw_sets, min_hits = _select_keyword_sets(pdf_path, all_sets, overrides)
        logger.info(
            "Triaging %s (%d keyword sets: %s, min_hits=%d)",
            pdf_path.name,
            len(kw_sets),
            ", ".join(kw_sets.keys()),
            min_hits,
        )
        result = triage_pdf(pdf_path, kw_sets, min_keyword_hits=min_hits)
        results.append(result)
        logger.info(
            "  → %d pages, %d target (%d substantive), recommendation=%s",
            result["total_pages"],
            result["estimated_target_pages_total"],
            result.get("substantive_target_pages_total", result["estimated_target_pages_total"]),
            result["extraction_recommendation"],
        )

    _write_report(results, REPORT_PATH)
    _write_json(results, JSON_PATH)

    return results


def run_single(
    pdf_path: Path,
    keyword_sets: dict[str, list[str]] | None = None,
    min_keyword_hits: int | None = None,
) -> dict:
    """Run triage on a single PDF (for testing)."""
    if keyword_sets is None:
        all_sets = load_keyword_sets()
        overrides = _load_overrides()
        keyword_sets, default_min = _select_keyword_sets(pdf_path, all_sets, overrides)
        if min_keyword_hits is None:
            min_keyword_hits = default_min
    return triage_pdf(pdf_path, keyword_sets, min_keyword_hits=min_keyword_hits or 2)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    run_batch()
