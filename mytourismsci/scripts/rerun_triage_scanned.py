"""Re-triage high-priority scanned PDFs using OCR fallback.

Inputs:  4 scanned PDFs + existing data/processed/pdf_triage.json
Outputs: Updated pdf_triage.json with OCR results merged in
Dependencies: src.ingestion.pdf_triage (with OCR), scripts.run_pdf_triage
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from src.ingestion.pdf_triage import load_keyword_sets, triage_pdf
from scripts.run_pdf_triage import (
    _load_overrides,
    _select_keyword_sets,
    _write_json,
    _write_report,
    JSON_PATH,
    REPORT_PATH,
)

TARGETS = [
    Path("docs/policy_documents/state_plans/Malaysia_Master_Plan_2022-2026.pdf"),
    Path("docs/policy_documents/state_plans/Penang_master_plan.pdf"),
    Path("docs/policy_documents/state_plans/Melaka_master_plan.pdf"),
    Path("data/raw/doe/doe_eqr_2025.pdf"),
]


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logger = logging.getLogger(__name__)

    all_sets = load_keyword_sets()
    overrides = _load_overrides()

    # Load existing results
    with open(JSON_PATH, encoding="utf-8") as f:
        existing: list[dict] = json.load(f)

    existing_by_name = {r["pdf_filename"]: i for i, r in enumerate(existing)}

    for pdf_path in TARGETS:
        if not pdf_path.exists():
            logger.warning("Target PDF not found: %s", pdf_path)
            continue

        kw_sets, min_hits = _select_keyword_sets(pdf_path, all_sets, overrides)
        logger.info(
            "Re-triaging %s with OCR (%d keyword sets: %s, min_hits=%d)",
            pdf_path.name, len(kw_sets), ", ".join(kw_sets.keys()), min_hits,
        )

        t0 = time.time()
        result = triage_pdf(pdf_path, kw_sets, min_keyword_hits=min_hits)
        elapsed = time.time() - t0

        subst = result.get("substantive_target_pages_total", 0)
        total_target = result.get("estimated_target_pages_total", 0)
        logger.info(
            "  → %d pages, %d target (%d substantive), ocr=%s, "
            "recommendation=%s, elapsed=%.0fs",
            result["total_pages"],
            total_target,
            subst,
            result.get("ocr_used", False),
            result["extraction_recommendation"],
            elapsed,
        )

        # Merge into existing results
        fname = pdf_path.name
        if fname in existing_by_name:
            existing[existing_by_name[fname]] = result
        else:
            existing.append(result)

    # Write updated outputs
    _write_json(existing, JSON_PATH)
    _write_report(existing, REPORT_PATH)
    logger.info("Done — updated %s and %s", JSON_PATH, REPORT_PATH)


if __name__ == "__main__":
    main()
