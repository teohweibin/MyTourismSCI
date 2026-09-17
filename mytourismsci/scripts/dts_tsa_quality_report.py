"""Data quality report for DTS and TSA ingested parquet outputs.

Reads the 6 parquet files produced by src/ingestion/excel_ingest.py and
prints completeness, value-range, and cross-validation checks.

Inputs:  data/processed/dts/*.parquet, data/processed/tsa/*.parquet
Outputs: stdout (text report)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DTS_DIR = Path("data/processed/dts")
TSA_DIR = Path("data/processed/tsa")

EXPECTED_STATES = sorted([
    "JOH", "KDH", "KTN", "MLK", "NSN", "PHG", "PNG", "PRK",
    "PLS", "SGR", "TRG", "SBH", "SWK", "KUL", "LBN", "PJY",
])
EXPECTED_YEARS = list(range(2020, 2026))


def _section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def _check_completeness(df: pd.DataFrame, name: str) -> None:
    total = df.size
    missing = df.isna().sum().sum()
    pct = (1 - missing / total) * 100 if total > 0 else 0
    print(f"  Completeness: {pct:.1f}% ({missing} missing of {total} cells)")
    for col in df.columns:
        col_missing = df[col].isna().sum()
        if col_missing > 0:
            print(f"    {col}: {col_missing} missing ({col_missing / len(df) * 100:.1f}%)")


def check_dts_jadual1() -> pd.DataFrame | None:
    path = DTS_DIR / "dts_jadual1.parquet"
    if not path.exists():
        print("  [MISSING] dts_jadual1.parquet not found")
        return None

    _section("DTS Jadual 1 — State Tourism Indicators")
    df = pd.read_parquet(path)
    print(f"  Shape: {df.shape[0]} rows x {df.shape[1]} cols")
    print(f"  Columns: {list(df.columns)}")

    states = sorted(df["state_code"].unique())
    years = sorted(df["year"].unique())
    indicators = sorted(df["indicator"].unique())
    print(f"  States ({len(states)}): {states}")
    print(f"  Years ({len(years)}): {years}")
    print(f"  Indicators ({len(indicators)}): {indicators}")

    missing_states = set(EXPECTED_STATES) - set(states)
    missing_years = set(EXPECTED_YEARS) - set(years)
    if missing_states:
        print(f"  [GAP] Missing states: {sorted(missing_states)}")
    if missing_years:
        print(f"  [GAP] Missing years: {sorted(missing_years)}")

    expected_rows = len(EXPECTED_STATES) * len(EXPECTED_YEARS) * len(indicators)
    print(f"  Expected rows (16 states x 6 years x {len(indicators)} indicators): {expected_rows}")
    print(f"  Actual rows: {len(df)}")
    if len(df) == expected_rows:
        print("  [OK] Row count matches expected")
    else:
        print(f"  [WARN] Row count differs by {abs(len(df) - expected_rows)}")

    _check_completeness(df, "jadual1")

    pivot = df.pivot_table(
        index=["state_code", "year"], columns="indicator", values="value", aggfunc="first"
    )
    for ind in indicators:
        vals = pivot[ind].dropna()
        if len(vals) > 0:
            print(f"  {ind}: min={vals.min():.2f}, max={vals.max():.2f}, mean={vals.mean():.2f}")

    return df


def check_dts_jadual10() -> pd.DataFrame | None:
    path = DTS_DIR / "dts_jadual10_od.parquet"
    if not path.exists():
        print("  [MISSING] dts_jadual10_od.parquet not found")
        return None

    _section("DTS Jadual 10 — Origin-Destination Matrix")
    df = pd.read_parquet(path)
    print(f"  Shape: {df.shape[0]} rows x {df.shape[1]} cols")

    years = sorted(df["file_year"].unique())
    origins = sorted(df["origin_code"].unique())
    dests = sorted(df["dest_code"].unique())
    print(f"  Years ({len(years)}): {years}")
    print(f"  Origins ({len(origins)}): {origins}")
    print(f"  Destinations ({len(dests)}): {dests}")

    expected_rows = len(EXPECTED_YEARS) * 16 * 16
    print(f"  Expected rows (6 years x 16x16 OD): {expected_rows}")
    print(f"  Actual rows: {len(df)}")
    if len(df) == expected_rows:
        print("  [OK] Row count matches expected")

    _check_completeness(df, "jadual10")

    vals = df["visitors_000"].dropna()
    print(f"  visitors_000: min={vals.min():.1f}, max={vals.max():.1f}, mean={vals.mean():.1f}")

    negatives = (vals < 0).sum()
    if negatives > 0:
        print(f"  [ERROR] {negatives} negative values found")
    else:
        print("  [OK] No negative values")

    return df


def check_dts_jadual14_15() -> pd.DataFrame | None:
    path = DTS_DIR / "dts_jadual14_15_hotels.parquet"
    if not path.exists():
        print("  [MISSING] dts_jadual14_15_hotels.parquet not found")
        return None

    _section("DTS Jadual 14 & 15 — Hotels and Rooms")
    df = pd.read_parquet(path)
    print(f"  Shape: {df.shape[0]} rows x {df.shape[1]} cols")
    print(f"  Columns: {list(df.columns)}")

    states = sorted(df["state_code"].unique())
    years = sorted(df["file_year"].unique())
    tables = sorted(df["table"].unique())
    print(f"  States ({len(states)}): {states}")
    print(f"  Years ({len(years)}): {years}")
    print(f"  Tables: {tables}")

    _check_completeness(df, "jadual14_15")

    for tbl in tables:
        sub = df[df["table"] == tbl]
        h = sub["hotels"].dropna()
        r = sub["rooms"].dropna()
        print(f"  {tbl}: {len(sub)} rows, hotels [{h.min():.0f}-{h.max():.0f}], rooms [{r.min():.0f}-{r.max():.0f}]")

    return df


def check_tsa_inbound() -> pd.DataFrame | None:
    path = TSA_DIR / "tsa_indicator_inbound.parquet"
    if not path.exists():
        print("  [MISSING] tsa_indicator_inbound.parquet not found")
        return None

    _section("TSA Indicator Inbound — National Tourism Indicators")
    df = pd.read_parquet(path)
    print(f"  Shape: {df.shape[0]} rows x {df.shape[1]} cols")

    years = sorted(df["year"].unique())
    indicators = sorted(df["indicator"].unique())
    print(f"  Years ({len(years)}): {years}")
    print(f"  Indicators ({len(indicators)}): {indicators}")

    _check_completeness(df, "tsa_inbound")

    for ind in indicators:
        vals = df.loc[df["indicator"] == ind, "value"].dropna()
        if len(vals) > 0:
            print(f"  {ind}: min={vals.min():.2f}, max={vals.max():.2f}")

    return df


def check_tsa_domestik() -> pd.DataFrame | None:
    path = TSA_DIR / "tsa_indicator_domestik.parquet"
    if not path.exists():
        print("  [MISSING] tsa_indicator_domestik.parquet not found")
        return None

    _section("TSA Indicator Domestik — State Domestic Visitors")
    df = pd.read_parquet(path)
    print(f"  Shape: {df.shape[0]} rows x {df.shape[1]} cols")

    states = sorted(df["state_code"].unique())
    years = sorted(df["year"].unique())
    print(f"  States ({len(states)}): {states}")
    print(f"  Years ({len(years)}): {years}")

    state_only = df[df["state_code"] != "NATIONAL"]
    state_codes = sorted(state_only["state_code"].unique())
    missing_states = set(EXPECTED_STATES) - set(state_codes)
    if missing_states:
        print(f"  [GAP] Missing states: {sorted(missing_states)}")
    else:
        print(f"  [OK] All 16 states present")

    _check_completeness(df, "tsa_domestik")

    vals = df["domestic_visitors_000"].dropna()
    print(f"  domestic_visitors_000: min={vals.min():.1f}, max={vals.max():.1f}, mean={vals.mean():.1f}")

    return df


def check_tsa_economic() -> pd.DataFrame | None:
    path = TSA_DIR / "tsa_economic.parquet"
    if not path.exists():
        print("  [MISSING] tsa_economic.parquet not found")
        return None

    _section("TSA Economic — GVA, GDP, Employment")
    df = pd.read_parquet(path)
    print(f"  Shape: {df.shape[0]} rows x {df.shape[1]} cols")

    years = sorted(df["year"].unique())
    indicators = sorted(df["indicator"].unique())
    print(f"  Years ({len(years)}): {years}")
    print(f"  Indicators ({len(indicators)}): {indicators}")

    _check_completeness(df, "tsa_economic")

    for ind in indicators:
        vals = df.loc[df["indicator"] == ind, "value"].dropna()
        if len(vals) > 0:
            print(f"  {ind}: min={vals.min():.2f}, max={vals.max():.2f}")

    growth_suspects = df[df["value"].apply(
        lambda v: isinstance(v, (int, float)) and -100 < v < 100
    )]
    econ_suspects = growth_suspects[growth_suspects["indicator"].isin(["gdp_rm_mil", "tourism_gva_rm_mil"])]
    if len(econ_suspects) > 0:
        print(f"  [WARN] {len(econ_suspects)} GDP/GVA values < 100 (possible growth rates)")
        print(econ_suspects.to_string(index=False))
    else:
        print("  [OK] No suspected growth rates in GDP/GVA values")

    return df


def cross_validate_dts_tsa(dts_j1: pd.DataFrame | None, tsa_dom: pd.DataFrame | None) -> None:
    _section("Cross-Validation: DTS Jadual 1 vs TSA Domestik")
    if dts_j1 is None or tsa_dom is None:
        print("  [SKIP] One or both datasets unavailable")
        return

    dts_visitors = dts_j1[dts_j1["indicator"] == "domestic_visitors_000"]
    tsa_state = tsa_dom[tsa_dom["state_code"] != "NATIONAL"]

    merged = dts_visitors.merge(
        tsa_state[["state_code", "year", "domestic_visitors_000"]],
        on=["state_code", "year"],
        how="inner",
    )
    if merged.empty:
        print("  [SKIP] No overlapping state-year pairs")
        return

    merged["diff_pct"] = (
        (merged["value"] - merged["domestic_visitors_000"])
        / merged["domestic_visitors_000"]
        * 100
    )
    print(f"  Matched {len(merged)} state-year pairs")
    print(f"  Mean absolute difference: {merged['diff_pct'].abs().mean():.1f}%")
    print(f"  Max absolute difference: {merged['diff_pct'].abs().max():.1f}%")

    large_diffs = merged[merged["diff_pct"].abs() > 20]
    if len(large_diffs) > 0:
        print(f"  [NOTE] {len(large_diffs)} pairs with >20% discrepancy (DTS vs TSA sources may differ)")
        for _, row in large_diffs.head(5).iterrows():
            print(f"    {row['state_code']} {row['year']}: DTS={row['value']:.0f}, TSA={row['domestic_visitors_000']:.0f} ({row['diff_pct']:+.1f}%)")
    else:
        print("  [OK] All pairs within 20% agreement")


def main() -> None:
    print("=" * 60)
    print("  MyTourismSCI — DTS & TSA Data Quality Report")
    print("=" * 60)

    dts_j1 = check_dts_jadual1()
    dts_j10 = check_dts_jadual10()
    dts_j14 = check_dts_jadual14_15()
    tsa_inb = check_tsa_inbound()
    tsa_dom = check_tsa_domestik()
    tsa_econ = check_tsa_economic()

    cross_validate_dts_tsa(dts_j1, tsa_dom)

    _section("Summary")
    datasets = {
        "DTS Jadual 1": dts_j1,
        "DTS Jadual 10": dts_j10,
        "DTS Jadual 14/15": dts_j14,
        "TSA Inbound": tsa_inb,
        "TSA Domestik": tsa_dom,
        "TSA Economic": tsa_econ,
    }
    for name, df in datasets.items():
        if df is not None:
            missing = df.isna().sum().sum()
            total = df.size
            pct = (1 - missing / total) * 100
            print(f"  {name:20s}: {len(df):>6} rows, {pct:.1f}% complete")
        else:
            print(f"  {name:20s}: [NOT AVAILABLE]")


if __name__ == "__main__":
    main()
