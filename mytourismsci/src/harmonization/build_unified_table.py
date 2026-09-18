"""Build the unified state-year indicator table.

Merges all processed parquet outputs from the ingestion pipeline into a
single wide-format table with one row per (state_code, year) pair and one
column per indicator. This is the sole input for AO1 composite index
construction.

Inputs:  Cleaned indicator files from data/processed/ and data/raw/
Outputs: data/final/state_year_indicators.parquet (wide)
         data/final/state_year_indicators_long.parquet (long, with pillar)
Dependencies: pandas, pyarrow
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_FINAL = PROJECT_ROOT / "data" / "final"

sys.path.insert(0, str(PROJECT_ROOT / "src"))
from harmonization.state_codes import VALID_CODES  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

TARGET_YEARS = list(range(2020, 2026))
TARGET_STATES = sorted(VALID_CODES)

PILLAR_MAP: dict[str, str] = {
    "tourism_receipts_rm_mil": "Economic",
    "expenditure_per_visitor": "Economic",
    "alos_nights": "Economic",
    "international_arrivals_share": "Economic",
    "tourism_concentration_ratio": "Economic",
    "wqi_annual": "Environmental",
    "waste_tonnes": "Environmental",
    "coastal_area_fraction": "Environmental",
    "pa_area_fraction": "Environmental",
    "green_hotel_share": "Environmental",
    "hotel_density_per_capita": "Social",
    "hh_water_access": "Social",
    "domestic_visitors_000": "Social",
    "tourism_trips_000": "Economic",
    "avg_expenditure_rm": "Economic",
    "dts_hotels_count": "Economic",
    "dts_rooms_count": "Economic",
    "population": "Social",
    "motac_hotels_rated_count": "Social",
    "green_hotel_count": "Environmental",
    "estimated_coastal_hotels": "Environmental",
    "estimated_pa_hotels": "Environmental",
    "n_rivers": "Environmental",
}


# ---------------------------------------------------------------------------
# Loader helpers
# ---------------------------------------------------------------------------

def _safe_read(path: Path, label: str) -> pd.DataFrame | None:
    if not path.exists():
        log.warning("MISSING: %s (%s)", label, path)
        return None
    df = pd.read_parquet(path)
    log.info(
        "Loaded %-40s  rows=%d  states=%s  years=%s  cols=%s",
        label,
        len(df),
        sorted(df["state_code"].dropna().unique()) if "state_code" in df.columns else "N/A",
        sorted(df["year"].unique()) if "year" in df.columns else "N/A",
        list(df.columns),
    )
    return df


def _scaffold() -> pd.DataFrame:
    """16 states x 6 years skeleton."""
    return pd.DataFrame(
        [(s, y) for s in TARGET_STATES for y in TARGET_YEARS],
        columns=["state_code", "year"],
    )


# ---------------------------------------------------------------------------
# Source-specific loaders — each returns (state_code, year, <indicator cols>)
# ---------------------------------------------------------------------------

def load_dts_jadual1() -> pd.DataFrame | None:
    df = _safe_read(DATA_PROCESSED / "dts" / "dts_jadual1.parquet", "dts_jadual1")
    if df is None:
        return None
    rename = {
        "avg_length_of_stay": "alos_nights",
        "avg_receipts_per_trip_rm": "avg_expenditure_rm",
    }
    df["indicator"] = df["indicator"].replace(rename)
    keep = [
        "domestic_visitors_000",
        "tourism_receipts_rm_mil",
        "tourism_trips_000",
        "alos_nights",
        "avg_expenditure_rm",
    ]
    df = df[df["indicator"].isin(keep)]
    wide = df.pivot_table(
        index=["state_code", "year"], columns="indicator", values="value", aggfunc="first"
    ).reset_index()
    wide.columns.name = None
    return wide


def load_dts_hotels() -> pd.DataFrame | None:
    df = _safe_read(
        DATA_PROCESSED / "dts" / "dts_jadual14_15_hotels.parquet", "dts_hotels"
    )
    if df is None:
        return None
    agg = (
        df.groupby(["state_code", "file_year"])
        .agg(dts_hotels_count=("hotels", "sum"), dts_rooms_count=("rooms", "sum"))
        .reset_index()
        .rename(columns={"file_year": "year"})
    )
    return agg


def load_population() -> pd.DataFrame | None:
    df = _safe_read(
        DATA_PROCESSED / "opendosm" / "population_state_raw.parquet", "population"
    )
    if df is None:
        return None
    df["year"] = df["year"].astype(int)
    return df[["state_code", "year", "population"]]


def load_hh_access() -> pd.DataFrame | None:
    df = _safe_read(
        DATA_PROCESSED / "opendosm" / "hh_access_amenities_raw.parquet", "hh_access"
    )
    if df is None:
        return None
    df["year"] = df["year"].astype(int)
    df = df.rename(columns={"piped_water": "hh_water_access"})
    result_rows = []
    for state in TARGET_STATES:
        sdf = df[df["state_code"] == state].sort_values("year")
        if sdf.empty:
            continue
        for target_year in TARGET_YEARS:
            candidates = sdf[sdf["year"] <= target_year]
            if candidates.empty:
                candidates = sdf
            row = candidates.iloc[-1]
            result_rows.append(
                {
                    "state_code": state,
                    "year": target_year,
                    "hh_water_access": row["hh_water_access"],
                }
            )
    return pd.DataFrame(result_rows)


def load_doe_wqi() -> pd.DataFrame | None:
    df = _safe_read(
        DATA_PROCESSED / "pdf_tables" / "doe_wqi_by_state_year.parquet", "doe_wqi"
    )
    if df is None:
        return None
    df["year"] = df["year"].astype(int)
    df = df[(df["year"] >= 2020) & (df["year"] <= 2025)]
    return df.rename(columns={"mean_wqi": "wqi_annual"})[
        ["state_code", "year", "wqi_annual", "n_rivers"]
    ]


def load_swcorp_waste() -> pd.DataFrame | None:
    df = _safe_read(
        DATA_PROCESSED / "pdf_tables" / "swcorp_waste_by_state.parquet", "swcorp_waste"
    )
    if df is None:
        return None
    df["year"] = df["year"].astype(int)
    return df.rename(columns={"value": "waste_tonnes"})[
        ["state_code", "year", "waste_tonnes"]
    ]


def load_geospatial() -> pd.DataFrame | None:
    df = _safe_read(
        DATA_PROCESSED / "geospatial" / "state_geospatial_indicators.parquet",
        "geospatial",
    )
    if df is None:
        return None
    cols = [
        "state_code",
        "coastal_area_fraction",
        "pa_area_fraction",
        "estimated_coastal_hotels",
        "estimated_pa_hotels",
    ]
    geo = df[[c for c in cols if c in df.columns]]
    rows = []
    for year in TARGET_YEARS:
        tmp = geo.copy()
        tmp["year"] = year
        rows.append(tmp)
    return pd.concat(rows, ignore_index=True)


def load_motac_rated() -> pd.DataFrame | None:
    df = _safe_read(DATA_RAW / "motac" / "motac_hotels_rated.parquet", "motac_rated")
    if df is None:
        return None
    counts = (
        df.groupby("state_code").size().reset_index(name="motac_hotels_rated_count")
    )
    rows = []
    for year in TARGET_YEARS:
        tmp = counts.copy()
        tmp["year"] = year
        rows.append(tmp)
    return pd.concat(rows, ignore_index=True)


def load_motac_green() -> pd.DataFrame | None:
    df = _safe_read(DATA_RAW / "motac" / "motac_hotels_green.parquet", "motac_green")
    if df is None:
        return None
    counts = df.groupby("state_code").size().reset_index(name="green_hotel_count")
    rows = []
    for year in TARGET_YEARS:
        tmp = counts.copy()
        tmp["year"] = year
        rows.append(tmp)
    return pd.concat(rows, ignore_index=True)


# ---------------------------------------------------------------------------
# Derived indicators
# ---------------------------------------------------------------------------

def compute_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Compute derived indicators from base columns."""
    if "domestic_visitors_000" in df.columns and "population" in df.columns:
        df["tourism_concentration_ratio"] = df["domestic_visitors_000"] / (
            df["population"]
        )

    if "tourism_receipts_rm_mil" in df.columns and "domestic_visitors_000" in df.columns:
        df["expenditure_per_visitor"] = (
            df["tourism_receipts_rm_mil"] * 1000 / df["domestic_visitors_000"]
        )

    if "motac_hotels_rated_count" in df.columns and "population" in df.columns:
        df["hotel_density_per_capita"] = (
            df["motac_hotels_rated_count"] / df["population"] * 100
        )

    if "green_hotel_count" in df.columns and "motac_hotels_rated_count" in df.columns:
        df["green_hotel_share"] = df["green_hotel_count"].fillna(0) / df[
            "motac_hotels_rated_count"
        ]

    df["international_arrivals_share"] = np.nan

    return df


# ---------------------------------------------------------------------------
# Quality checks
# ---------------------------------------------------------------------------

def quality_report(df: pd.DataFrame) -> str:
    lines = ["# Data Quality Report", ""]
    lines.append(f"Shape: {df.shape[0]} rows x {df.shape[1]} columns")
    lines.append(f"Expected: {len(TARGET_STATES)} states x {len(TARGET_YEARS)} years = {len(TARGET_STATES)*len(TARGET_YEARS)} rows")
    lines.append("")
    lines.append("## Per-column completeness")
    lines.append("")
    lines.append(f"{'Column':<35} {'Non-null':>8} {'Total':>6} {'%':>7}")
    lines.append("-" * 60)
    indicator_cols = [c for c in df.columns if c not in ("state_code", "year")]
    for col in sorted(indicator_cols):
        nn = df[col].notna().sum()
        pct = nn / len(df) * 100
        lines.append(f"{col:<35} {nn:>8} {len(df):>6} {pct:>6.1f}%")

    lines.append("")
    lines.append("## State-year rows with ALL indicators missing")
    lines.append("")
    all_missing = df[df[indicator_cols].isna().all(axis=1)]
    if len(all_missing) == 0:
        lines.append("None — every row has at least one non-null indicator.")
    else:
        for _, row in all_missing.iterrows():
            lines.append(f"  {row['state_code']} {row['year']}")
        lines.append(f"\nTotal: {len(all_missing)} rows with complete missingness.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Long format conversion
# ---------------------------------------------------------------------------

def to_long_format(wide: pd.DataFrame) -> pd.DataFrame:
    indicator_cols = [c for c in wide.columns if c not in ("state_code", "year")]
    long = wide.melt(
        id_vars=["state_code", "year"],
        value_vars=indicator_cols,
        var_name="indicator_name",
        value_name="value",
    )
    long["pillar"] = long["indicator_name"].map(PILLAR_MAP).fillna("Unassigned")
    return long.sort_values(["state_code", "year", "pillar", "indicator_name"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_unified_table() -> pd.DataFrame:
    """Load all sources, merge, compute derived indicators, and return wide table."""
    scaffold = _scaffold()
    log.info("Scaffold: %d rows (%d states x %d years)", len(scaffold), len(TARGET_STATES), len(TARGET_YEARS))

    loaders = [
        load_dts_jadual1,
        load_dts_hotels,
        load_population,
        load_hh_access,
        load_doe_wqi,
        load_swcorp_waste,
        load_geospatial,
        load_motac_rated,
        load_motac_green,
    ]

    merged = scaffold.copy()
    for loader in loaders:
        result = loader()
        if result is not None:
            result["year"] = result["year"].astype(int)
            merged = merged.merge(result, on=["state_code", "year"], how="left")
            log.info("After merge: %d cols", merged.shape[1])

    merged = compute_derived(merged)
    log.info("Final wide table: %s", merged.shape)
    return merged


def main() -> None:
    DATA_FINAL.mkdir(parents=True, exist_ok=True)

    wide = build_unified_table()

    report = quality_report(wide)
    print(report)

    wide_path = DATA_FINAL / "state_year_indicators.parquet"
    wide.to_parquet(wide_path, index=False, engine="pyarrow")
    log.info("Written wide format: %s", wide_path)

    long = to_long_format(wide)
    long_path = DATA_FINAL / "state_year_indicators_long.parquet"
    long.to_parquet(long_path, index=False, engine="pyarrow")
    log.info("Written long format: %s", long_path)

    unassigned = long[long["pillar"] == "Unassigned"]["indicator_name"].unique()
    if len(unassigned) > 0:
        log.warning("Indicators without pillar assignment: %s", list(unassigned))


if __name__ == "__main__":
    main()
