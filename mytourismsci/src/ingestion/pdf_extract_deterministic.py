"""Deterministic table extraction from PDF reports using triage-identified target pages.

Extracts structured tabular data from DOE Environmental Quality Reports and
SWCorp annual reports using pdfplumber, guided by target pages identified
during the triage phase. No LLM calls are made.

Inputs:  data/processed/pdf_triage.json, PDF files in data/raw/
Outputs: Parquet files in data/processed/pdf_tables/
Dependencies: pdfplumber, pandas, src.harmonization.state_codes
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import pandas as pd
import pdfplumber

from src.harmonization.state_codes import normalize_state_name, VALID_CODES

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRIAGE_PATH = PROJECT_ROOT / "data" / "processed" / "pdf_triage.json"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "pdf_tables"
REPORT_PATH = PROJECT_ROOT / "outputs" / "pdf_extract_deterministic_report.md"

ALL_STATE_CODES = sorted(VALID_CODES)


def _load_triage() -> list[dict]:
    with open(TRIAGE_PATH, encoding="utf-8") as f:
        return json.load(f)


def _get_triage_entries(
    triage: list[dict],
    filename_pattern: str,
    topic: str | None = None,
) -> list[dict]:
    """Filter triage entries by filename glob and optional topic."""
    results = []
    for entry in triage:
        fn = entry["pdf_filename"]
        if not re.search(filename_pattern, fn, re.IGNORECASE):
            continue
        if topic and topic not in entry.get("target_pages_by_topic", {}):
            continue
        results.append(entry)
    return results


def _page_numbers_from_topic(entry: dict, topic: str) -> list[int]:
    """Extract page numbers from triage entry's target_pages_by_topic.

    Target pages are stored as dicts with a 'page' key or as plain ints.
    """
    pages_raw = entry.get("target_pages_by_topic", {}).get(topic, [])
    result = []
    for item in pages_raw:
        if isinstance(item, dict):
            result.append(item["page"])
        else:
            result.append(int(item))
    return sorted(set(result))


def _extract_tables_from_pages(
    pdf_path: Path,
    page_numbers: list[int],
) -> list[tuple[int, list[list]]]:
    """Extract tables from specific pages of a PDF.

    Returns list of (page_number, table_rows) tuples.
    """
    results = []
    with pdfplumber.open(pdf_path) as pdf:
        for pg_num in page_numbers:
            if pg_num < 1 or pg_num > len(pdf.pages):
                logger.warning("Page %d out of range for %s", pg_num, pdf_path.name)
                continue
            page = pdf.pages[pg_num - 1]
            tables = page.extract_tables()
            for table in tables:
                if table and len(table) > 2:
                    results.append((pg_num, table))
    return results


def _safe_normalize_state(name: str) -> str | None:
    """Attempt state normalization, return None on failure."""
    if not name or not isinstance(name, str):
        return None
    cleaned = name.strip().rstrip("/")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return None

    for candidate in [cleaned, cleaned.replace("WP ", "W.P. ")]:
        try:
            return normalize_state_name(candidate)
        except ValueError:
            continue

    if cleaned.lower() in ("wilayah persekutuan", "wp"):
        return "KUL"

    return None


def _parse_wqi_value(val: str | None) -> float | None:
    """Parse a WQI value from table cell, returning None for non-numeric."""
    if val is None:
        return None
    val = str(val).strip()
    if not val or val in ("-", "New", "Baru", "N/A", ""):
        return None
    val = val.replace(",", "")
    try:
        return float(val)
    except ValueError:
        return None


def _detect_year_columns(header_row1: list, header_row2: list) -> list[tuple[int, int]]:
    """Detect which columns contain year-indexed WQI values.

    Returns list of (column_index, year) tuples.
    """
    year_cols = []
    for i, cell in enumerate(header_row2):
        if cell is None:
            continue
        cell_text = str(cell).strip()
        match = re.search(r"IKA|WQI", cell_text, re.IGNORECASE)
        if match:
            year_match = re.search(r"(20\d{2})", str(header_row1[i] or "") + " " + cell_text)
            if year_match:
                year_cols.append((i, int(year_match.group(1))))

    if not year_cols:
        for i, cell in enumerate(header_row2):
            if cell is None:
                continue
            cell_text = str(cell).strip()
            year_match = re.match(r"^(20\d{2})$", cell_text)
            if year_match:
                year_cols.append((i, int(year_match.group(1))))

    return year_cols


def _is_wqi_table_header(row: list) -> bool:
    """Check if a row is a WQI table header."""
    if not row:
        return False
    first = str(row[0] or "").upper()
    return "NEGERI" in first or "STATE" in first


def _parse_doe_wqi_tables(
    tables: list[tuple[int, list[list]]],
    report_year: int,
) -> pd.DataFrame:
    """Parse DOE WQI river-level tables into a long-format DataFrame."""
    all_rows: list[dict] = []
    current_state: str | None = None

    for page_num, table in tables:
        if len(table) < 3:
            continue

        if not _is_wqi_table_header(table[0]):
            continue

        year_cols = _detect_year_columns(table[0], table[1])
        if not year_cols:
            for i, cell in enumerate(table[0]):
                if cell is None:
                    continue
                year_match = re.search(r"(20\d{2})", str(cell))
                if year_match:
                    year_cols.append((i, int(year_match.group(1))))
            if not year_cols:
                logger.debug("No year columns detected on page %d", page_num)
                continue

        for row in table[2:]:
            state_cell = str(row[0] or "").strip() if row[0] else ""
            if state_cell:
                resolved = _safe_normalize_state(state_cell)
                if resolved:
                    current_state = resolved

            if current_state is None:
                continue

            basin = str(row[1] or "").strip() if len(row) > 1 else ""
            river = str(row[2] or "").strip() if len(row) > 2 else ""

            if not basin and not river:
                continue

            for col_idx, year in year_cols:
                if col_idx >= len(row):
                    continue
                wqi = _parse_wqi_value(row[col_idx])
                if wqi is not None and 0 < wqi <= 100:
                    all_rows.append({
                        "state_code": current_state,
                        "year": year,
                        "river_basin": basin,
                        "river": river,
                        "wqi": wqi,
                        "source_page": page_num,
                        "source_report": report_year,
                    })

    if not all_rows:
        return pd.DataFrame()

    return pd.DataFrame(all_rows)


def extract_doe_wqi() -> pd.DataFrame:
    """Extract WQI data from all DOE Environmental Quality Reports.

    Produces a long-format DataFrame with state-level mean WQI per year,
    aggregated from river-level measurements.
    """
    triage = _load_triage()
    doe_entries = _get_triage_entries(triage, r"doe_eqr_\d{4}\.pdf", "water_quality")

    if not doe_entries:
        logger.warning("No DOE EQR entries found in triage")
        return pd.DataFrame()

    all_river_data: list[pd.DataFrame] = []

    for entry in doe_entries:
        pdf_path = PROJECT_ROOT / entry["pdf_path"]
        if not pdf_path.exists():
            logger.warning("PDF not found: %s", pdf_path)
            continue

        if not entry.get("text_extractable", True):
            logger.info("Skipping non-text-extractable %s", entry["pdf_filename"])
            continue

        year_match = re.search(r"(\d{4})", entry["pdf_filename"])
        report_year = int(year_match.group(1)) if year_match else 0

        wq_pages = _page_numbers_from_topic(entry, "water_quality")
        if not wq_pages:
            continue

        logger.info(
            "Extracting DOE WQI from %s (%d target pages)",
            entry["pdf_filename"],
            len(wq_pages),
        )

        tables = _extract_tables_from_pages(pdf_path, wq_pages)
        wqi_tables = [(pg, t) for pg, t in tables if _is_wqi_table_header(t[0])]

        if not wqi_tables:
            logger.warning("No WQI tables found in %s", entry["pdf_filename"])
            continue

        df = _parse_doe_wqi_tables(wqi_tables, report_year)
        if not df.empty:
            all_river_data.append(df)
            logger.info(
                "  %s: %d river-level records across %d years",
                entry["pdf_filename"],
                len(df),
                df["year"].nunique(),
            )

    if not all_river_data:
        logger.error("No WQI data extracted from any DOE report")
        return pd.DataFrame()

    river_df = pd.concat(all_river_data, ignore_index=True)
    river_df = river_df.drop_duplicates(
        subset=["state_code", "year", "river_basin", "river"],
        keep="last",
    )

    state_year_wqi = (
        river_df.groupby(["state_code", "year"])["wqi"]
        .agg(["mean", "count"])
        .reset_index()
        .rename(columns={"mean": "mean_wqi", "count": "n_rivers"})
    )
    state_year_wqi["mean_wqi"] = state_year_wqi["mean_wqi"].round(2)

    logger.info(
        "DOE WQI extraction complete: %d state-year records, years %d-%d",
        len(state_year_wqi),
        int(state_year_wqi["year"].min()),
        int(state_year_wqi["year"].max()),
    )

    return state_year_wqi


def _parse_swcorp_state_table(
    table: list[list],
    value_col_label: str | None = None,
) -> pd.DataFrame:
    """Parse a simple NEGERI/JUMLAH table from SWCorp reports."""
    rows: list[dict] = []
    for row in table:
        if len(row) < 2:
            continue
        state_raw = str(row[0] or "").strip()
        if not state_raw or "NEGERI" in state_raw.upper() or "JUMLAH" == state_raw.upper():
            continue

        state_code = _safe_normalize_state(state_raw)
        if state_code is None:
            state_raw_clean = re.sub(r"\s+", " ", state_raw)
            if state_raw_clean.upper() in ("JUMLAH", "TOTAL"):
                continue
            logger.warning("SWCorp state parse failure: %r", state_raw)
            continue

        val_str = str(row[1] or "").strip().replace(",", "")
        try:
            value = float(val_str)
        except (ValueError, TypeError):
            continue

        rows.append({"state_code": state_code, "value": value})

    return pd.DataFrame(rows)


def extract_swcorp_waste() -> pd.DataFrame:
    """Extract waste data from SWCorp annual reports.

    Searches for state-level waste disposal tables across all available
    SWCorp report years. Only accepts tables with plausible tonnage values
    (>100) to avoid picking up facility/contractor count tables.
    """
    swcorp_dir = PROJECT_ROOT / "data" / "raw" / "swcorp"
    if not swcorp_dir.exists():
        logger.warning("SWCorp directory not found: %s", swcorp_dir)
        return pd.DataFrame()

    pdf_files = sorted(swcorp_dir.glob("swcorp_*.pdf"))
    if not pdf_files:
        logger.warning("No SWCorp PDFs found")
        return pd.DataFrame()

    all_records: list[dict] = []

    for pdf_path in pdf_files:
        year_match = re.search(r"(\d{4})", pdf_path.name)
        report_year = int(year_match.group(1)) if year_match else 0

        logger.info("Scanning SWCorp %d for waste-by-state tables...", report_year)

        with pdfplumber.open(pdf_path) as pdf:
            for pg_idx, page in enumerate(pdf.pages):
                pg_num = pg_idx + 1
                tables = page.extract_tables()
                for table in tables:
                    if not table or len(table) < 4:
                        continue

                    header_text = str(table[0][0] or "").upper()
                    is_waste_volume = (
                        "SISA" in header_text
                        and ("DILUPUSKAN" in header_text or "PELUPUSAN" in header_text)
                        and "BILANGAN" not in header_text
                        and "KONTRAKTOR" not in header_text
                    )

                    if not is_waste_volume:
                        continue

                    header_row_idx = 0
                    for r in range(min(3, len(table))):
                        cell = str(table[r][0] or "").upper().strip()
                        if cell == "NEGERI" or "NEGERI" in cell:
                            header_row_idx = r
                            break

                    data_rows = table[header_row_idx + 1:]
                    df = _parse_swcorp_state_table(
                        [table[header_row_idx]] + data_rows
                    )

                    if df.empty or len(df) < 3:
                        continue

                    if df["value"].max() < 100:
                        logger.debug(
                            "  Skipping table on page %d (max value %.1f too small for tonnage)",
                            pg_num, df["value"].max(),
                        )
                        continue

                    df["year"] = report_year
                    df["source_page"] = pg_num
                    df["metric"] = "construction_waste_disposed_tonnes"
                    all_records.append(df)
                    logger.info(
                        "  Found waste table on page %d: %d states, total=%.1f",
                        pg_num, len(df), df["value"].sum(),
                    )

    if not all_records:
        logger.warning("No SWCorp waste-by-state tables extracted")
        return pd.DataFrame()

    result = pd.concat(all_records, ignore_index=True)
    result = result.drop_duplicates(
        subset=["state_code", "year", "metric"], keep="last"
    )

    logger.info(
        "SWCorp extraction complete: %d records across %d years",
        len(result),
        result["year"].nunique(),
    )

    return result


def _validate_output(
    df: pd.DataFrame,
    source_name: str,
    state_col: str = "state_code",
    value_cols: list[str] | None = None,
) -> list[str]:
    """Validate extracted data and return list of warnings."""
    warnings: list[str] = []

    if df.empty:
        warnings.append(f"{source_name}: no data extracted")
        return warnings

    present_states = set(df[state_col].dropna().unique())
    missing_states = sorted(set(ALL_STATE_CODES) - present_states)
    if missing_states:
        warnings.append(
            f"{source_name}: missing {len(missing_states)} states: "
            f"{', '.join(missing_states)}"
        )

    if value_cols is None:
        value_cols = [c for c in df.select_dtypes(include="number").columns
                      if c not in ("year", "source_page", "source_report")]

    for col in value_cols:
        neg_count = (df[col] < 0).sum()
        if neg_count > 0:
            warnings.append(
                f"{source_name}: {neg_count} negative values in column '{col}'"
            )

    return warnings


def _write_report(
    results: dict[str, pd.DataFrame],
    all_warnings: dict[str, list[str]],
) -> None:
    """Generate data quality report."""
    lines = [
        f"# Deterministic PDF Table Extraction Report",
        f"",
        f"## Summary",
        f"",
    ]

    for source, df in results.items():
        if df.empty:
            lines.append(f"- **{source}**: no data extracted")
        else:
            states = df["state_code"].nunique() if "state_code" in df.columns else 0
            years = df["year"].nunique() if "year" in df.columns else 0
            lines.append(
                f"- **{source}**: {len(df)} records, "
                f"{states} states, {years} years"
            )

    lines.extend(["", "## Per-Source Detail", ""])

    for source, df in results.items():
        lines.append(f"### {source}")
        lines.append("")

        if df.empty:
            lines.append("No data extracted from this source.")
            lines.append("")
            continue

        if "year" in df.columns:
            years = sorted(df["year"].unique())
            lines.append(f"- Years covered: {min(years)}-{max(years)}")

        if "state_code" in df.columns:
            states = sorted(df["state_code"].dropna().unique())
            lines.append(f"- States present ({len(states)}): {', '.join(states)}")
            missing = sorted(set(ALL_STATE_CODES) - set(states))
            if missing:
                lines.append(f"- **Missing states ({len(missing)})**: {', '.join(missing)}")

        value_cols = [c for c in df.select_dtypes(include="number").columns
                      if c not in ("year", "source_page", "source_report", "n_rivers")]

        for col in value_cols:
            s = df[col].dropna()
            if not s.empty:
                lines.append(
                    f"- {col}: min={s.min():.2f}, max={s.max():.2f}, "
                    f"mean={s.mean():.2f}, missing={df[col].isna().sum()}"
                )

        lines.append("")

        warnings = all_warnings.get(source, [])
        if warnings:
            lines.append("**Warnings:**")
            for w in warnings:
                lines.append(f"- {w}")
            lines.append("")

        if "year" in df.columns and "state_code" in df.columns:
            lines.append("**Coverage matrix (states x years):**")
            lines.append("")
            pivot = df.groupby(["year", "state_code"]).size().unstack(fill_value=0)
            lines.append(pivot.to_markdown())
            lines.append("")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote report -> %s", REPORT_PATH)


def run_all() -> dict[str, pd.DataFrame]:
    """Run all deterministic PDF table extractions."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results: dict[str, pd.DataFrame] = {}
    all_warnings: dict[str, list[str]] = {}

    logger.info("=== DOE WQI Extraction ===")
    doe_wqi = extract_doe_wqi()
    results["doe_wqi_by_state_year"] = doe_wqi
    all_warnings["doe_wqi_by_state_year"] = _validate_output(
        doe_wqi, "doe_wqi_by_state_year", value_cols=["mean_wqi"]
    )
    if not doe_wqi.empty:
        out = OUTPUT_DIR / "doe_wqi_by_state_year.parquet"
        doe_wqi.to_parquet(out, index=False)
        logger.info("Wrote DOE WQI -> %s (%d rows)", out, len(doe_wqi))

    logger.info("=== SWCorp Waste Extraction ===")
    swcorp = extract_swcorp_waste()
    results["swcorp_waste_by_state"] = swcorp
    all_warnings["swcorp_waste_by_state"] = _validate_output(
        swcorp, "swcorp_waste_by_state", value_cols=["value"]
    )
    if not swcorp.empty:
        out = OUTPUT_DIR / "swcorp_waste_by_state.parquet"
        swcorp.to_parquet(out, index=False)
        logger.info("Wrote SWCorp waste -> %s (%d rows)", out, len(swcorp))

    _write_report(results, all_warnings)

    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    run_all()
