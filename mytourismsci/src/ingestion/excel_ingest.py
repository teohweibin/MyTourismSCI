"""Ingest DTS (Domestic Tourism Survey) state Excel files and national TSA
(Tourism Satellite Account) Excel files for MyTourismSCI.

DTS files provide state-level tourism indicators (visitors, expenditure,
trips, accommodation, origin-destination) across Malaysia's 16 states.
Files are organised by year (2020–2025) with varying naming conventions.

TSA files provide national-level tourism economic accounts (GDP contribution,
employment, inbound/domestic indicators) from the Tourism Satellite Account.

Entry-point functions
---------------------
ingest_dts_state_files(input_dir, output_dir)
    Parse all DTS state Excel files across year subdirectories,
    extracting Jadual 1, 10, and 14 & 15, and write consolidated
    parquet outputs.

ingest_tsa_national(input_dir, output_dir)
    Parse TSA Excel files (Indicator Inbound, Indicator Domestik,
    Jad 4/5/7), and write consolidated parquet outputs.

Inputs:  Excel files in data/raw/dts/ and data/raw/tsa/
Outputs: Parquet files in data/processed/dts/ and data/processed/tsa/
Dependencies: pandas, python-calamine, pyarrow
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

from src.harmonization.state_codes import CANONICAL_STATE_CODES, normalize_state_name

logger = logging.getLogger(__name__)

DTS_INPUT_DIR = Path("data/raw/dts")
TSA_INPUT_DIR = Path("data/raw/tsa")
DTS_OUTPUT_DIR = Path("data/processed/dts")
TSA_OUTPUT_DIR = Path("data/processed/tsa")

# Naming patterns across DTS survey years:
#   2018-2020: "Table of Publication_[State Name].xlsx"
#   2021, 2024-2025: "[State]_dts_[YYYY].xlsx" (title case, underscores)
#   2022-2023: "[state]_dts_[YYYY].xlsx" (lowercase, no word separators)
#   2025 has 3 files missing .xlsx extension (KL, Labuan, Putrajaya)
_PATTERN_TABLE_OF_PUB = re.compile(
    r"Table of Publication_(.+)\.xlsx$", re.IGNORECASE
)
_PATTERN_STATE_DTS = re.compile(
    r"(.+?)_dts_(\d{4})(?:\.xlsx)?$", re.IGNORECASE
)

# Filename stems that need special handling for state name resolution
_FILENAME_STATE_ALIASES: dict[str, str] = {
    "negerisembilan": "Negeri Sembilan",
    "pulaupinang": "Pulau Pinang",
    "kualalumpur": "W.P. Kuala Lumpur",
    "kl": "W.P. Kuala Lumpur",
    "labuan": "W.P. Labuan",
    "putrajaya": "W.P. Putrajaya",
    "kuala_lumpur": "W.P. Kuala Lumpur",
    "negeri_sembilan": "Negeri Sembilan",
    "pulau_pinang": "Pulau Pinang",
}


def _extract_state_from_filename(filename: str) -> str | None:
    """Extract a raw state name string from a DTS filename.

    Returns the raw state string (not yet normalised to a code) or None
    if the filename does not match any known DTS naming convention.
    """
    m = _PATTERN_TABLE_OF_PUB.match(filename)
    if m:
        return m.group(1).strip()

    m = _PATTERN_STATE_DTS.match(filename)
    if m:
        raw = m.group(1).strip()
        key = raw.lower().replace(" ", "")
        if key in _FILENAME_STATE_ALIASES:
            return _FILENAME_STATE_ALIASES[key]
        cleaned = raw.replace("_", " ")
        return cleaned

    return None


def discover_dts_files(
    input_dir: Path = DTS_INPUT_DIR,
    read_sheets: bool = False,
) -> list[dict]:
    """Scan data/raw/dts/ for DTS Excel files across year subdirectories.

    Parameters
    ----------
    input_dir : Path
        Root directory containing year-subdirectories.
    read_sheets : bool
        If True, open each file to read sheet names (slow for many files).

    Returns
    -------
    list[dict]
        Each dict has keys: path (Path), year (int), state_code (str),
        raw_state (str). If read_sheets is True, also sheets (list[str]).
    """
    results: list[dict] = []
    if not input_dir.exists():
        logger.warning("DTS input directory not found: %s", input_dir)
        return results

    for year_dir in sorted(input_dir.iterdir()):
        if not year_dir.is_dir():
            continue
        try:
            year = int(year_dir.name)
        except ValueError:
            continue

        for fpath in sorted(year_dir.iterdir()):
            if fpath.is_dir():
                continue

            raw_state = _extract_state_from_filename(fpath.name)
            if raw_state is None:
                logger.warning("Unrecognised DTS filename: %s", fpath)
                continue

            try:
                state_code = normalize_state_name(raw_state)
            except ValueError:
                logger.warning(
                    "Could not normalise state %r from %s", raw_state, fpath
                )
                continue

            entry: dict = {
                "path": fpath,
                "year": year,
                "state_code": state_code,
                "raw_state": raw_state,
            }

            if read_sheets:
                try:
                    import openpyxl
                    wb = openpyxl.load_workbook(fpath, read_only=True)
                    entry["sheets"] = wb.sheetnames
                    wb.close()
                except Exception as exc:
                    logger.warning("Could not read sheets from %s: %s", fpath, exc)
                    entry["sheets"] = []

            results.append(entry)

    return results


def discover_tsa_files(
    input_dir: Path = TSA_INPUT_DIR,
    read_sheets: bool = False,
) -> list[dict]:
    """Scan data/raw/tsa/ for TSA Excel files.

    Parameters
    ----------
    input_dir : Path
        Directory containing TSA Excel files (tourism_YYYY.xlsx).
    read_sheets : bool
        If True, open each file to read sheet names.

    Returns
    -------
    list[dict]
        Each dict has keys: path (Path), year (int).
        If read_sheets is True, also sheets (list[str]).
    """
    results: list[dict] = []
    if not input_dir.exists():
        logger.warning("TSA input directory not found: %s", input_dir)
        return results

    for fpath in sorted(input_dir.glob("tourism_*.xlsx")):
        m = re.match(r"tourism_(\d{4})\.xlsx$", fpath.name)
        if not m:
            continue
        year = int(m.group(1))

        entry: dict = {"path": fpath, "year": year}

        if read_sheets:
            try:
                import openpyxl
                wb = openpyxl.load_workbook(fpath, read_only=True)
                entry["sheets"] = wb.sheetnames
                wb.close()
            except Exception as exc:
                logger.warning("Could not read sheets from %s: %s", fpath, exc)
                entry["sheets"] = []

        results.append(entry)

    return results


# Jadual 1 row identification: match English portion of bilingual labels.
# Rows alternate value / growth-rate — we extract only value rows.
_JADUAL1_INDICATORS: list[tuple[str, str]] = [
    ("receipts per capita", "avg_receipts_per_capita_rm"),
    ("receipts per trip", "avg_receipts_per_trip_rm"),
    ("total receipts", "tourism_receipts_rm_mil"),
    ("tourism receipts", "tourism_receipts_rm_mil"),
    ("domestic visitor", "domestic_visitors_000"),
    ("tourism trip", "tourism_trips_000"),
    ("length of stay", "avg_length_of_stay"),
]


def _extract_english_label(cell_value: str) -> str:
    """Extract the English portion from a bilingual cell label."""
    if not isinstance(cell_value, str):
        return ""
    parts = cell_value.split("\n")
    if len(parts) >= 2:
        return parts[-1].strip()
    if "|" in cell_value:
        return cell_value.split("|")[-1].strip()
    return cell_value.strip()


def _parse_jadual1_from_df(
    df_raw: pd.DataFrame,
    state_code: str,
    file_year: int,
) -> pd.DataFrame:
    """Parse Jadual 1 from a pre-loaded DataFrame."""
    # Row 3 (0-indexed) is the header; extract year columns
    header_row = df_raw.iloc[3]
    year_cols: dict[int, int] = {}
    for col_idx in range(1, len(header_row)):
        val = header_row.iloc[col_idx]
        if pd.notna(val):
            try:
                yr = int(float(val))
                if 2000 <= yr <= 2030:
                    year_cols[col_idx] = yr
            except (ValueError, TypeError):
                continue

    if not year_cols:
        logger.warning("No year columns found in Jadual 1 of %s", filepath)
        return pd.DataFrame(columns=["state_code", "year", "indicator", "value"])

    # Filter to 2020-2025
    year_cols = {c: y for c, y in year_cols.items() if 2020 <= y <= 2025}
    if not year_cols:
        logger.info("No years in 2020-2025 range in Jadual 1 of %s", filepath)
        return pd.DataFrame(columns=["state_code", "year", "indicator", "value"])

    records: list[dict] = []
    for row_idx in range(4, len(df_raw)):
        label_raw = df_raw.iloc[row_idx, 0]
        if pd.isna(label_raw):
            continue
        label_lower = str(label_raw).lower()

        # Skip growth rate rows
        if "peratus" in label_lower or "growth rate" in label_lower or "percentage change" in label_lower:
            continue

        eng_label = _extract_english_label(str(label_raw)).lower()
        matched_indicator = None
        for keyword, indicator_name in _JADUAL1_INDICATORS:
            if keyword in eng_label:
                matched_indicator = indicator_name
                break

        if matched_indicator is None:
            continue

        for col_idx, yr in year_cols.items():
            val = df_raw.iloc[row_idx, col_idx]
            if pd.notna(val):
                try:
                    val = float(val)
                except (ValueError, TypeError):
                    val = pd.NA
            else:
                val = pd.NA
            records.append({
                "state_code": state_code,
                "year": yr,
                "indicator": matched_indicator,
                "value": val,
            })

    result = pd.DataFrame(records)
    if not result.empty:
        result = result.sort_values(["indicator", "year"]).reset_index(drop=True)
    return result


def parse_dts_jadual1(
    filepath: Path,
    state_code: str,
    file_year: int,
) -> pd.DataFrame:
    """Parse Jadual 1 (key tourism statistics) from a DTS Excel file."""
    df_raw = pd.read_excel(
        filepath, sheet_name="Jadual 1", header=None, engine="calamine"
    )
    return _parse_jadual1_from_df(df_raw, state_code, file_year)


_OD_STATE_NAMES = [
    "Malaysia", "Johor", "Kedah", "Kelantan", "Melaka", "Negeri Sembilan",
    "Pahang", "Pulau Pinang", "Perak", "Perlis", "Selangor", "Terengganu",
    "Sabah", "Sarawak", "W.P. Kuala Lumpur", "W.P. Labuan", "W.P. Putrajaya",
]


def _parse_jadual10_from_df(
    df_raw: pd.DataFrame,
    state_code: str,
    file_year: int,
) -> pd.DataFrame:
    """Parse Jadual 10 from a pre-loaded DataFrame."""
    # Identify destination columns from row 6
    dest_row = df_raw.iloc[6]
    dest_cols: dict[int, str] = {}
    for col_idx in range(3, len(dest_row)):
        val = dest_row.iloc[col_idx]
        if pd.notna(val) and str(val).strip():
            dest_cols[col_idx] = str(val).strip()

    if not dest_cols:
        logger.warning("No destination columns found in Jadual 10 of %s", filepath)
        return pd.DataFrame(columns=["file_year", "origin_code", "dest_code", "visitors_000"])

    records: list[dict] = []
    for row_idx in range(8, min(24, len(df_raw))):
        origin_raw = df_raw.iloc[row_idx, 2]
        if pd.isna(origin_raw) or not str(origin_raw).strip():
            continue
        origin_name = str(origin_raw).strip()
        try:
            origin_code = normalize_state_name(origin_name)
        except ValueError:
            continue

        for col_idx, dest_name in dest_cols.items():
            try:
                dest_code = normalize_state_name(dest_name)
            except ValueError:
                continue

            val = df_raw.iloc[row_idx, col_idx]
            if pd.notna(val):
                try:
                    val = float(val)
                except (ValueError, TypeError):
                    val = pd.NA
            else:
                val = pd.NA

            records.append({
                "file_year": file_year,
                "origin_code": origin_code,
                "dest_code": dest_code,
                "visitors_000": val,
            })

    result = pd.DataFrame(records)
    if not result.empty:
        result = result.sort_values(["origin_code", "dest_code"]).reset_index(drop=True)
    return result


def parse_dts_jadual10(
    filepath: Path,
    state_code: str,
    file_year: int,
) -> pd.DataFrame:
    """Parse Jadual 10 (tourists by state visited) — origin-destination matrix."""
    df_raw = pd.read_excel(
        filepath, sheet_name="Jadual 10", header=None, engine="calamine"
    )
    return _parse_jadual10_from_df(df_raw, state_code, file_year)


_STAR_RATING_LABELS: dict[str, str] = {
    "5-bintang": "5-star",
    "5-star": "5-star",
    "4-bintang": "4-star",
    "4-star": "4-star",
    "3-bintang": "3-star",
    "3-star": "3-star",
    "2-bintang": "2-star",
    "2-star": "2-star",
    "1-bintang": "1-star",
    "1-star": "1-star",
    "3 orkid": "3-orchid",
    "3 orchid": "3-orchid",
    "2 orkid": "2-orchid",
    "2 orchid": "2-orchid",
    "1 orkid": "1-orchid",
    "1 orchid": "1-orchid",
    "unrated": "unrated",
}


def _parse_jadual14_15_from_df(
    df_raw: pd.DataFrame,
    state_code: str,
    file_year: int,
) -> pd.DataFrame:
    """Parse Jadual 14 & 15 from a pre-loaded DataFrame."""
    records: list[dict] = []

    # Jadual 14: star ratings (rows 4-12)
    for row_idx in range(4, min(13, len(df_raw))):
        label_raw = df_raw.iloc[row_idx, 0]
        if pd.isna(label_raw):
            continue
        label_str = str(label_raw).strip().lower()
        # Match against known rating labels
        matched = None
        for key, canonical in _STAR_RATING_LABELS.items():
            if key in label_str:
                matched = canonical
                break
        if matched is None:
            continue

        hotels = df_raw.iloc[row_idx, 2]
        rooms = df_raw.iloc[row_idx, 5]

        records.append({
            "state_code": state_code,
            "file_year": file_year,
            "table": "star_rating",
            "category": matched,
            "hotels": int(hotels) if pd.notna(hotels) else pd.NA,
            "rooms": int(rooms) if pd.notna(rooms) else pd.NA,
        })

    # Jadual 15: location (search for the location header then parse rows below)
    loc_start = None
    for row_idx in range(14, min(30, len(df_raw))):
        val = df_raw.iloc[row_idx, 0]
        if pd.notna(val) and "location" in str(val).lower():
            loc_start = row_idx + 1
            break

    _LOCATION_LABELS = {
        "bandar": "city_town",
        "city": "city_town",
        "pantai": "beach",
        "beach": "beach",
        "gunung": "hill",
        "hill": "hill",
        "lain": "others",
        "others": "others",
    }

    if loc_start is not None:
        for row_idx in range(loc_start, min(loc_start + 6, len(df_raw))):
            label_raw = df_raw.iloc[row_idx, 0]
            if pd.isna(label_raw):
                continue
            label_str = str(label_raw).strip().lower()
            if "jumlah" in label_str or "total" in label_str:
                continue

            matched_loc = None
            for key, canonical in _LOCATION_LABELS.items():
                if key in label_str:
                    matched_loc = canonical
                    break
            if matched_loc is None:
                continue

            hotels = df_raw.iloc[row_idx, 2]
            rooms = df_raw.iloc[row_idx, 5]

            records.append({
                "state_code": state_code,
                "file_year": file_year,
                "table": "location",
                "category": matched_loc,
                "hotels": int(hotels) if pd.notna(hotels) else pd.NA,
                "rooms": int(rooms) if pd.notna(rooms) else pd.NA,
            })

    return pd.DataFrame(records)


def ingest_dts_state_files(
    input_dir: Path = DTS_INPUT_DIR,
    output_dir: Path = DTS_OUTPUT_DIR,
) -> dict[str, pd.DataFrame]:
    """Parse all DTS state Excel files and write consolidated parquet outputs.

    Parameters
    ----------
    input_dir : Path
        Root directory containing year-subdirectories of DTS Excel files.
    output_dir : Path
        Directory to write output parquet files.

    Returns
    -------
    dict[str, pd.DataFrame]
        Mapping of output name to DataFrame for each parsed table type.
    """
    files = discover_dts_files(input_dir)
    # Filter to 2020-2025
    files = [f for f in files if 2020 <= f["year"] <= 2025]
    logger.info("Found %d DTS files in 2020-2025 range", len(files))

    all_jadual1: list[pd.DataFrame] = []
    all_jadual10: list[pd.DataFrame] = []
    all_jadual14_15: list[pd.DataFrame] = []

    target_sheets = ["Jadual 1", "Jadual 10", "Jadual 14 & 15"]

    for entry in files:
        fp = entry["path"]
        sc = entry["state_code"]
        yr = entry["year"]
        logger.info("Parsing %s %d: %s", sc, yr, fp.name)

        # Read all 3 sheets in one open to avoid 3x file I/O
        try:
            sheets = pd.read_excel(
                fp, sheet_name=target_sheets, header=None, engine="calamine"
            )
        except Exception as exc:
            logger.error("Could not open %s: %s", fp, exc)
            continue

        try:
            df1 = _parse_jadual1_from_df(sheets["Jadual 1"], sc, yr)
            all_jadual1.append(df1)
        except Exception as exc:
            logger.error("Jadual 1 failed for %s %d: %s", sc, yr, exc)

        try:
            df10 = _parse_jadual10_from_df(sheets["Jadual 10"], sc, yr)
            all_jadual10.append(df10)
        except Exception as exc:
            logger.error("Jadual 10 failed for %s %d: %s", sc, yr, exc)

        try:
            df14 = _parse_jadual14_15_from_df(sheets["Jadual 14 & 15"], sc, yr)
            all_jadual14_15.append(df14)
        except Exception as exc:
            logger.error("Jadual 14&15 failed for %s %d: %s", sc, yr, exc)

    results: dict[str, pd.DataFrame] = {}
    output_dir.mkdir(parents=True, exist_ok=True)

    if all_jadual1:
        combined = pd.concat(all_jadual1, ignore_index=True)
        # Deduplicate: keep latest file_year's value for each state/year/indicator
        combined = combined.sort_values(
            ["state_code", "year", "indicator"]
        ).drop_duplicates(
            subset=["state_code", "year", "indicator"], keep="last"
        ).reset_index(drop=True)
        path = output_dir / "dts_jadual1.parquet"
        combined.to_parquet(path, index=False)
        results["jadual1"] = combined
        logger.info("Wrote %s (%d rows)", path, len(combined))

    if all_jadual10:
        combined = pd.concat(all_jadual10, ignore_index=True)
        # Deduplicate: keep latest file_year for each year's OD pair
        combined = combined.sort_values(
            ["file_year", "origin_code", "dest_code"]
        ).drop_duplicates(
            subset=["file_year", "origin_code", "dest_code"], keep="last"
        ).reset_index(drop=True)
        path = output_dir / "dts_jadual10_od.parquet"
        combined.to_parquet(path, index=False)
        results["jadual10"] = combined
        logger.info("Wrote %s (%d rows)", path, len(combined))

    if all_jadual14_15:
        combined = pd.concat(all_jadual14_15, ignore_index=True)
        combined = combined.sort_values(
            ["state_code", "file_year", "table", "category"]
        ).drop_duplicates(
            subset=["state_code", "file_year", "table", "category"], keep="last"
        ).reset_index(drop=True)
        path = output_dir / "dts_jadual14_15_hotels.parquet"
        combined.to_parquet(path, index=False)
        results["jadual14_15"] = combined
        logger.info("Wrote %s (%d rows)", path, len(combined))

    return results


def parse_dts_jadual14_15(
    filepath: Path,
    state_code: str,
    file_year: int,
) -> pd.DataFrame:
    """Parse Jadual 14 & 15 (hotels/rooms by star rating and location)."""
    df_raw = pd.read_excel(
        filepath, sheet_name="Jadual 14 & 15", header=None, engine="calamine"
    )
    return _parse_jadual14_15_from_df(df_raw, state_code, file_year)


def _parse_tsa_year_columns(header_row: pd.Series) -> dict[int, int]:
    """Extract year -> column-index mapping from a TSA header row."""
    year_cols: dict[int, int] = {}
    for col_idx in range(1, len(header_row)):
        val = header_row.iloc[col_idx]
        if pd.isna(val):
            continue
        try:
            yr = int(float(str(val).rstrip("ep")))
            if 2020 <= yr <= 2025:
                year_cols[col_idx] = yr
        except (ValueError, TypeError):
            continue
    return year_cols


def _parse_tsa_indicator_inbound(filepath: Path) -> pd.DataFrame:
    """Parse Indicator Inbound sheet for national-level arrival and accommodation data."""
    df_raw = pd.read_excel(
        filepath, sheet_name="Indicator Inbound", header=None, engine="calamine"
    )

    year_cols = _parse_tsa_year_columns(df_raw.iloc[2])

    _INBOUND_INDICATORS: list[tuple[str, str]] = [
        ("visitor arrivals to malaysia from selected", "visitor_arrivals_total"),
        ("tourist arrivals to malaysia", "tourist_arrivals"),
        ("excursionist arrivals", "excursionist_arrivals"),
        ("number of hotels", "num_hotels_national"),
        ("number of rooms", "num_rooms_national"),
        ("number of guests", "num_guests_total"),
        ("average length of stay", "avg_los_inbound"),
        ("average occupancy rate", "avg_occupancy_rate_pct"),
    ]

    records: list[dict] = []
    for row_idx in range(4, len(df_raw)):
        label_raw = df_raw.iloc[row_idx, 0]
        label_raw_c1 = df_raw.iloc[row_idx, 1]
        label = ""
        if pd.notna(label_raw):
            label = str(label_raw)
        if pd.notna(label_raw_c1):
            label = str(label_raw_c1) if not label else label

        if not label:
            continue
        label_lower = label.lower()
        if "peratus" in label_lower or "percentage change" in label_lower:
            continue

        matched = None
        for keyword, ind_name in _INBOUND_INDICATORS:
            if keyword in label_lower:
                matched = ind_name
                break
        if matched is None:
            continue

        for col_idx, yr in year_cols.items():
            val = df_raw.iloc[row_idx, col_idx]
            if pd.notna(val):
                try:
                    val = float(str(val).replace("*", "").strip())
                except (ValueError, TypeError):
                    val = pd.NA
            else:
                val = pd.NA
            records.append({"year": yr, "indicator": matched, "value": val})

    return pd.DataFrame(records).sort_values(["indicator", "year"]).reset_index(drop=True)


def _parse_tsa_indicator_domestik(filepath: Path) -> pd.DataFrame:
    """Parse Indicator Domestik sheet for state-level domestic visitor counts."""
    df_raw = pd.read_excel(
        filepath, sheet_name="Indicator Domestik", header=None, engine="calamine"
    )

    year_cols = _parse_tsa_year_columns(df_raw.iloc[2])

    records: list[dict] = []
    # State rows are 7-22 (0-indexed), column 1 has state names
    for row_idx in range(7, min(24, len(df_raw))):
        state_raw = df_raw.iloc[row_idx, 1]
        if pd.isna(state_raw):
            continue
        state_name = str(state_raw).strip()
        try:
            state_code = normalize_state_name(state_name)
        except ValueError:
            continue

        for col_idx, yr in year_cols.items():
            val = df_raw.iloc[row_idx, col_idx]
            if pd.notna(val):
                try:
                    val = float(val)
                except (ValueError, TypeError):
                    val = pd.NA
            else:
                val = pd.NA
            records.append({
                "state_code": state_code,
                "year": yr,
                "domestic_visitors_000": val,
                "indicator": "domestic_visitors_000",
            })

    # Also extract national aggregate indicators from rows 24+
    _NATIONAL_INDICATORS = [
        ("number of visitors", "domestic_visitors_total_000"),
        ("number of tourists", "domestic_tourists_000"),
        ("number of excursionists", "domestic_excursionists_000"),
        ("numbers of tourism trips", "domestic_trips_000"),
        ("overnight trips", "domestic_overnight_trips_000"),
        ("same day trips", "domestic_sameday_trips_000"),
        ("average length of stay", "domestic_avg_los"),
    ]
    for row_idx in range(24, min(35, len(df_raw))):
        label_raw = df_raw.iloc[row_idx, 1]
        if pd.isna(label_raw):
            continue
        label_lower = str(label_raw).lower()
        if "peratus" in label_lower or "percentage" in label_lower:
            continue

        matched = None
        for keyword, ind_name in _NATIONAL_INDICATORS:
            if keyword in label_lower:
                matched = ind_name
                break
        if matched is None:
            continue

        for col_idx, yr in year_cols.items():
            val = df_raw.iloc[row_idx, col_idx]
            if pd.notna(val):
                try:
                    val = float(val)
                except (ValueError, TypeError):
                    val = pd.NA
            else:
                val = pd.NA
            records.append({
                "state_code": "NATIONAL",
                "year": yr,
                "domestic_visitors_000": val,
                "indicator": matched,
            })

    result = pd.DataFrame(records)
    if not result.empty:
        result = result.sort_values(
            ["state_code", "year"]
        ).reset_index(drop=True)
    return result


def _parse_tsa_economic_tables(filepath: Path) -> pd.DataFrame:
    """Parse Jad 5 (tourism GVA/GDP) and Jad 7 (employment) into long format."""
    records: list[dict] = []

    # --- Jad 5: Tourism GVA and GDP ---
    df5 = pd.read_excel(
        filepath, sheet_name="Jad 5", header=None, engine="calamine"
    )
    year_cols_5 = _parse_tsa_year_columns(df5.iloc[2])

    _JAD5_INDICATORS = [
        ("jumlah nilai ditambah kasar", "tourism_gva_rm_mil"),
        ("total gross value added", "tourism_gva_rm_mil"),
        ("keluaran dalam negeri kasar", "gdp_rm_mil"),
        ("gross domestic product", "gdp_rm_mil"),
    ]
    for row_idx in range(5, min(20, len(df5))):
        label_raw = df5.iloc[row_idx, 0]
        # Also check col 1 for "percentage change" header
        label_c1 = df5.iloc[row_idx, 1] if len(df5.columns) > 1 else None
        c1_lower = str(label_c1).lower() if pd.notna(label_c1) else ""
        if "peratus" in c1_lower or "percentage" in c1_lower:
            break  # Everything below is growth rates

        if pd.isna(label_raw):
            continue
        label_lower = str(label_raw).lower()

        matched = None
        for keyword, ind_name in _JAD5_INDICATORS:
            if keyword in label_lower:
                matched = ind_name
                break
        if matched is None:
            continue

        for col_idx, yr in year_cols_5.items():
            val = df5.iloc[row_idx, col_idx]
            if pd.notna(val):
                try:
                    val = float(str(val).replace("..", "").strip())
                except (ValueError, TypeError):
                    val = pd.NA
            else:
                val = pd.NA
            records.append({"year": yr, "indicator": matched, "value": val})

    # --- Jad 7: Employment ---
    df7 = pd.read_excel(
        filepath, sheet_name="Jad 7", header=None, engine="calamine"
    )
    year_cols_7 = _parse_tsa_year_columns(df7.iloc[2])

    # Row 14 (0-indexed 13) is the total employment row
    for row_idx in range(5, min(20, len(df7))):
        label_raw = df7.iloc[row_idx, 0]
        if pd.isna(label_raw):
            continue
        label_lower = str(label_raw).lower()
        if "jumlah" in label_lower or "total" in label_lower:
            for col_idx, yr in year_cols_7.items():
                val = df7.iloc[row_idx, col_idx]
                if pd.notna(val):
                    try:
                        val = float(val)
                    except (ValueError, TypeError):
                        val = pd.NA
                else:
                    val = pd.NA
                records.append({
                    "year": yr,
                    "indicator": "tourism_employment_000",
                    "value": val,
                })
            break

    result = pd.DataFrame(records)
    if not result.empty:
        result = result.sort_values(["indicator", "year"]).reset_index(drop=True)
    return result


def ingest_tsa_national(
    input_dir: Path = TSA_INPUT_DIR,
    output_dir: Path = TSA_OUTPUT_DIR,
) -> dict[str, pd.DataFrame]:
    """Parse TSA Excel files and write consolidated parquet outputs.

    Parameters
    ----------
    input_dir : Path
        Directory containing TSA Excel files (tourism_YYYY.xlsx).
    output_dir : Path
        Directory to write output parquet files.

    Returns
    -------
    dict[str, pd.DataFrame]
        Mapping of output name to DataFrame for each parsed sheet.
    """
    files = discover_tsa_files(input_dir)
    # Filter to 2020-2025 (use the file with the latest year that covers our range)
    files = [f for f in files if f["year"] >= 2020]
    logger.info("Found %d TSA files (2020+)", len(files))

    results: dict[str, pd.DataFrame] = {}
    output_dir.mkdir(parents=True, exist_ok=True)

    # Use latest TSA file for national indicators (it contains all prior years)
    latest = max(files, key=lambda f: f["year"]) if files else None
    if latest is None:
        logger.error("No TSA files found in %s", input_dir)
        return results

    fp = latest["path"]
    logger.info("Using %s as primary TSA source", fp.name)

    # --- Indicator Inbound ---
    try:
        df_inb = _parse_tsa_indicator_inbound(fp)
        path = output_dir / "tsa_indicator_inbound.parquet"
        df_inb.to_parquet(path, index=False)
        results["indicator_inbound"] = df_inb
        logger.info("Wrote %s (%d rows)", path, len(df_inb))
    except Exception as exc:
        logger.error("Indicator Inbound failed: %s", exc)

    # --- Indicator Domestik (state-level) ---
    try:
        df_dom = _parse_tsa_indicator_domestik(fp)
        path = output_dir / "tsa_indicator_domestik.parquet"
        df_dom.to_parquet(path, index=False)
        results["indicator_domestik"] = df_dom
        logger.info("Wrote %s (%d rows)", path, len(df_dom))
    except Exception as exc:
        logger.error("Indicator Domestik failed: %s", exc)

    # --- Jad 5 (Tourism GVA + GDP share) + Jad 7 (Employment) ---
    try:
        df_econ = _parse_tsa_economic_tables(fp)
        path = output_dir / "tsa_economic.parquet"
        df_econ.to_parquet(path, index=False)
        results["economic"] = df_econ
        logger.info("Wrote %s (%d rows)", path, len(df_econ))
    except Exception as exc:
        logger.error("TSA economic tables failed: %s", exc)

    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("=== DTS State File Ingestion ===")
    dts_results = ingest_dts_state_files()

    logger.info("=== TSA National File Ingestion ===")
    tsa_results = ingest_tsa_national()
