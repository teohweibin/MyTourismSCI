"""AO3: Policy commitment gap analysis.

Compares LLM-extracted policy commitments against observed MyTourismSCI
indicator trajectories to classify each commitment as already_met,
on_track, at_risk, or off_track.

Methodology: Required annual change vs. observed compound annual growth
rate (CAGR) 2020–2025, following OECD/JRC (2008) Handbook Section 2
on target-vs-trajectory benchmarking.

Inputs:  data/processed/policy_commitments.parquet
         outputs/mytourismsci_scores.parquet
         data/final/state_year_indicators.parquet
Outputs: outputs/ao3_gap_analysis.parquet
         outputs/state_briefs/{state_code}.md
         outputs/ao3_national_synthesis.md
Dependencies: pandas, numpy
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DATA_FINAL = PROJECT_ROOT / "data" / "final"
OUTPUTS = PROJECT_ROOT / "outputs"
BRIEFS_DIR = OUTPUTS / "state_briefs"

STATE_NAMES = {
    "JOH": "Johor", "KDH": "Kedah", "KTN": "Kelantan", "MLK": "Melaka",
    "NSN": "Negeri Sembilan", "PHG": "Pahang", "PNG": "Pulau Pinang",
    "PRK": "Perak", "PLS": "Perlis", "SGR": "Selangor", "TRG": "Terengganu",
    "SBH": "Sabah", "SWK": "Sarawak", "KUL": "Kuala Lumpur",
    "LBN": "Labuan", "PJY": "Putrajaya",
}

# --- Commitment-to-indicator mapping ---
# Each entry: (indicator_column, unit_conversion_factor, notes)
# factor converts commitment target_value into indicator units.
COMMITMENT_MAP: dict[str, dict] = {
    "visitor_arrivals": {
        "indicator": "domestic_visitors_000",
        "notes": "Domestic visitors in thousands",
    },
    "tourism_receipts": {
        "indicator": "tourism_receipts_rm_mil",
        "notes": "Tourism receipts in RM millions",
    },
}

UNMAPPABLE_TYPES = {"employment", "other", "waste_reduction", "green_hotels"}


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    commitments = pd.read_parquet(DATA_PROCESSED / "policy_commitments.parquet")
    scores = pd.read_parquet(OUTPUTS / "mytourismsci_scores.parquet")
    indicators = pd.read_parquet(DATA_FINAL / "state_year_indicators.parquet")
    log.info(
        "Loaded %d commitments, %d score rows, %d indicator rows",
        len(commitments), len(scores), len(indicators),
    )
    return commitments, scores, indicators


def inspect_commitments(df: pd.DataFrame) -> None:
    log.info("--- Commitment value counts ---")
    for col in ["commitment_type", "state", "sustainability_dimension", "target_year"]:
        log.info("\n%s:\n%s", col, df[col].value_counts().sort_index().to_string())


def filter_usable(df: pd.DataFrame) -> pd.DataFrame:
    mask = (
        (df["target_year"] >= 2025)
        & df["target_value"].notna()
        & (df["confidence"] != "low")
    )
    usable = df[mask].copy()
    log.info(
        "Usable commitments: %d / %d (filtered: target_year>=2025, "
        "target_value not null, confidence != low)",
        len(usable), len(df),
    )
    log.info(
        "Usable per state:\n%s",
        usable["state"].value_counts().to_string(),
    )
    return usable


def _convert_target_to_indicator_units(row: pd.Series) -> tuple[float | None, str]:
    """Convert a commitment's target_value to indicator-comparable units.

    Returns (converted_value, reason_if_unmappable).
    """
    ctype = row["commitment_type"]
    unit = str(row.get("target_unit", "")).lower()
    val = row["target_value"]

    if ctype == "visitor_arrivals":
        if "international" in unit:
            return None, "no_state_international_arrivals"
        if "million" in unit:
            return val * 1000.0, ""  # millions → thousands
        if "percent" in unit and "growth" in unit:
            return None, "growth_rate_target"  # needs special handling
        if val > 100_000:
            return val / 1000.0, ""  # absolute count → thousands
        return val, ""

    if ctype == "tourism_receipts":
        if "billion" in unit:
            return val * 1000.0, ""  # RM billion → RM million
        if "million" in unit:
            return val, ""  # already RM million
        if "percent" in unit and "gdp" in unit.lower():
            return None, "gdp_share_target"
        return val, ""

    if ctype == "hotel_rooms":
        if "percent" in unit and "occupancy" in unit:
            return None, "occupancy_rate_target"
        return val, ""

    return None, "unmappable_type"


def _get_indicator_value(
    indicators: pd.DataFrame, state: str, indicator: str, year: int,
) -> float | None:
    """Get most recent observed value for state+indicator, preferring given year."""
    if state == "national":
        # Aggregate across all states
        subset = indicators[indicators["year"] == year]
        if subset.empty or indicator not in subset.columns:
            return None
        val = subset[indicator].sum()
        return float(val) if pd.notna(val) else None

    subset = indicators[
        (indicators["state_code"] == state) & (indicators["year"] == year)
    ]
    if subset.empty or indicator not in subset.columns:
        return None
    val = subset[indicator].iloc[0]
    return float(val) if pd.notna(val) else None


def _compute_cagr(
    indicators: pd.DataFrame, state: str, indicator: str,
    year_start: int = 2020, year_end: int = 2025,
) -> float | None:
    """Compute compound annual growth rate for an indicator."""
    v_start = _get_indicator_value(indicators, state, indicator, year_start)
    v_end = _get_indicator_value(indicators, state, indicator, year_end)
    if v_start is None or v_end is None or v_start <= 0 or v_end <= 0:
        return None
    n = year_end - year_start
    if n <= 0:
        return None
    return (v_end / v_start) ** (1.0 / n) - 1.0


def classify_gap(
    current: float, target: float, target_year: int,
    observed_cagr: float | None, reference_year: int = 2025,
) -> tuple[str, float, float]:
    """Classify commitment gap status.

    Returns (status, required_annual_change, observed_annual_change).
    """
    if current >= target:
        return "already_met", 0.0, 0.0

    years_remaining = target_year - reference_year
    if years_remaining <= 0:
        if current >= target:
            return "already_met", 0.0, 0.0
        return "off_track", float("inf"), 0.0

    required_annual = (target - current) / years_remaining

    if observed_cagr is not None and current > 0:
        observed_annual = current * observed_cagr
    else:
        observed_annual = 0.0

    if observed_annual >= 0.9 * required_annual:
        status = "on_track"
    elif observed_annual >= 0.5 * required_annual:
        status = "at_risk"
    else:
        status = "off_track"

    return status, required_annual, observed_annual


def compute_gap_analysis(
    usable: pd.DataFrame, indicators: pd.DataFrame,
) -> pd.DataFrame:
    results = []
    unmappable_log = []

    for _, row in usable.iterrows():
        ctype = row["commitment_type"]
        state = row["state"]

        if ctype in UNMAPPABLE_TYPES or ctype not in COMMITMENT_MAP:
            unmappable_log.append({
                "state": state,
                "commitment_type": ctype,
                "reason": "no_matching_indicator",
            })
            continue

        converted_target, skip_reason = _convert_target_to_indicator_units(row)
        if converted_target is None:
            unmappable_log.append({
                "state": state,
                "commitment_type": ctype,
                "reason": skip_reason,
            })
            continue

        mapping = COMMITMENT_MAP[ctype]
        indicator = mapping["indicator"]
        current = _get_indicator_value(indicators, state, indicator, 2025)
        if current is None:
            current = _get_indicator_value(indicators, state, indicator, 2024)

        if current is None:
            unmappable_log.append({
                "state": state,
                "commitment_type": ctype,
                "reason": "no_observed_value",
            })
            continue

        cagr = _compute_cagr(indicators, state, indicator)

        status, req_annual, obs_annual = classify_gap(
            current, converted_target, row["target_year"], cagr,
        )

        results.append({
            "state": state,
            "commitment_type": ctype,
            "indicator": indicator,
            "target_value": row["target_value"],
            "target_unit": row["target_unit"],
            "target_converted": converted_target,
            "target_year": row["target_year"],
            "current_value": current,
            "observed_cagr": cagr,
            "observed_annual_change": obs_annual,
            "required_annual_change": req_annual,
            "status": status,
            "verbatim_quote": row["verbatim_quote"],
            "source_doc": row["source_doc"],
            "source_page": row["source_page"],
            "sustainability_dimension": row["sustainability_dimension"],
        })

    if unmappable_log:
        umdf = pd.DataFrame(unmappable_log)
        log.info(
            "Unmappable commitments (%d):\n%s",
            len(umdf),
            umdf.groupby(["reason", "commitment_type"]).size().to_string(),
        )

    gap_df = pd.DataFrame(results)
    if not gap_df.empty:
        log.info(
            "Gap classifications:\n%s",
            gap_df["status"].value_counts().to_string(),
        )
    return gap_df


def generate_state_brief(
    state: str,
    gap_df: pd.DataFrame,
    scores: pd.DataFrame,
    indicators: pd.DataFrame,
    total_extracted_for_state: int = 0,
) -> str:
    state_code = state if state != "national" else None
    name = STATE_NAMES.get(state, state.title())

    if state_code:
        s25 = scores[
            (scores["state_code"] == state_code) & (scores["year"] == 2025)
        ]
        s20 = scores[
            (scores["state_code"] == state_code) & (scores["year"] == 2020)
        ]
    else:
        name = "National (aggregate)"
        s25 = s20 = pd.DataFrame()

    lines = [f"# {name} — Policy Gap Brief\n"]

    if state == "SWK" and total_extracted_for_state > 0:
        lines.append(
            f"> **Note:** Sarawak has {total_extracted_for_state} extracted commitments "
            "but none map to current MyTourismSCI observable indicators "
            "(targets are expressed as GDP shares and annual growth rates "
            "rather than absolute visitor/receipts values captured in the "
            "composite). Sarawak's committed sustainability trajectory "
            "should be discussed qualitatively in the main report using "
            "the extracted commitments in "
            "`data/processed/policy_commitments.parquet` filtered for "
            "state=SWK.\n"
        )

    if not s25.empty:
        r = s25.iloc[0]
        lines.append(
            f"**MyTourismSCI 2025:** {r['mytourismsci_score']:.3f} "
            f"(rank {int(r['rank'])} / 16)\n"
        )
    else:
        lines.append("**MyTourismSCI 2025:** N/A (national aggregate)\n")

    lines.append("## Pillar Trajectory (2020 → 2025)\n")
    if not s25.empty and not s20.empty:
        r25 = s25.iloc[0]
        r20 = s20.iloc[0]
        lines.append("| Pillar | 2020 | 2025 | Delta |")
        lines.append("|--------|------|------|-------|")
        for p in ["economic_score", "environmental_score", "social_score"]:
            pname = p.replace("_score", "").title()
            v20 = r20[p]
            v25 = r25[p]
            delta = v25 - v20
            sign = "+" if delta >= 0 else ""
            lines.append(f"| {pname} | {v20:.3f} | {v25:.3f} | {sign}{delta:.3f} |")
        lines.append("")
    else:
        lines.append("*(National-level pillar trajectory not applicable)*\n")

    state_gaps = gap_df[gap_df["state"] == state].copy()
    if state_gaps.empty:
        lines.append("## Commitments\n")
        lines.append("No directly mappable commitments for gap analysis.\n")
    else:
        lines.append("## Commitment Gap Analysis\n")
        lines.append(
            "| Commitment | Target | Year | Current | Status | Source |"
        )
        lines.append(
            "|------------|--------|------|---------|--------|--------|"
        )
        for _, g in state_gaps.iterrows():
            lines.append(
                f"| {g['commitment_type']} | {g['target_value']:,.1f} "
                f"{g['target_unit']} | {int(g['target_year'])} | "
                f"{g['current_value']:,.1f} | **{g['status']}** | "
                f"{g['source_doc']} p.{int(g['source_page'])} |"
            )
        lines.append("")

        lines.append(f"> {state_gaps.iloc[0]['verbatim_quote']}\n")
        lines.append(f"*Source: {state_gaps.iloc[0]['source_doc']}, "
                      f"p.{int(state_gaps.iloc[0]['source_page'])}*\n")

    off_track = state_gaps[state_gaps["status"].isin(["off_track", "at_risk"])]
    if not off_track.empty:
        lines.append("## Priority Interventions\n")
        for _, g in off_track.iterrows():
            lines.append(
                f"- **{g['commitment_type']}** ({g['status']}): current "
                f"{g['current_value']:,.1f} vs. target "
                f"{g['target_value']:,.1f} {g['target_unit']} by "
                f"{int(g['target_year'])}. Required annual change: "
                f"{g['required_annual_change']:,.1f}; observed: "
                f"{g['observed_annual_change']:,.1f}."
            )
        lines.append("")

    return "\n".join(lines)


def generate_national_synthesis(
    gap_df: pd.DataFrame,
    total_commitments: int,
    unmappable_types: list[str],
) -> str:
    lines = ["# AO3 National Synthesis — Policy Commitment Gap Analysis\n"]

    lines.append("## Coverage\n")
    lines.append(
        f"- **Commitments analysed (mappable):** {len(gap_df)} / "
        f"{total_commitments} extracted"
    )
    mapped_types = gap_df["commitment_type"].unique().tolist() if not gap_df.empty else []
    lines.append(f"- **Mapped commitment types:** {', '.join(mapped_types)}")
    lines.append(
        f"- **Unmappable types (no matching indicator):** "
        f"{', '.join(sorted(set(unmappable_types)))}"
    )
    lines.append(
        "- **States with zero commitments in source data:** "
        "Sabah, Kedah, Perak, Melaka, Pulau Pinang, Negeri Sembilan, "
        "Pahang, Kelantan, Terengganu, Selangor, Labuan, Putrajaya "
        "(coverage limitation of available policy documents)\n"
    )

    if gap_df.empty:
        lines.append("No mappable commitments for quantitative gap analysis.\n")
        return "\n".join(lines)

    lines.append("## Status Breakdown\n")
    status_counts = gap_df["status"].value_counts()
    lines.append("| Status | Count |")
    lines.append("|--------|-------|")
    for s in ["already_met", "on_track", "at_risk", "off_track"]:
        lines.append(f"| {s} | {status_counts.get(s, 0)} |")
    lines.append("")

    lines.append("## By Sustainability Dimension\n")
    if "sustainability_dimension" in gap_df.columns:
        ct = pd.crosstab(gap_df["sustainability_dimension"], gap_df["status"])
        lines.append(ct.to_markdown())
        lines.append("")

    lines.append("## Key Findings\n")
    n_met = status_counts.get("already_met", 0)
    n_on = status_counts.get("on_track", 0)
    n_risk = status_counts.get("at_risk", 0)
    n_off = status_counts.get("off_track", 0)
    total_mapped = len(gap_df)

    findings = []

    if n_met > 0:
        met_rows = gap_df[gap_df["status"] == "already_met"]
        states_met = ", ".join(met_rows["state"].unique())
        findings.append(
            f"{n_met} of {total_mapped} mappable commitments are already "
            f"met as of 2025, concentrated in: {states_met}."
        )

    if n_on > 0:
        findings.append(
            f"{n_on} commitment(s) classified as on-track, where observed "
            f"annual change meets at least 90% of required pace."
        )

    if n_off > 0:
        off_rows = gap_df[gap_df["status"] == "off_track"]
        findings.append(
            f"{n_off} commitment(s) classified as off-track — observed "
            f"growth falls below 50% of the required annual change. "
            f"States affected: {', '.join(off_rows['state'].unique())}."
        )

    if n_risk > 0:
        findings.append(
            f"{n_risk} commitment(s) at risk — growth trajectory covers "
            f"50–90% of required pace, requiring policy acceleration."
        )

    findings.append(
        "The majority of extracted commitments (employment targets, "
        "sectoral growth rates, GDP-share targets) cannot be mapped to "
        "available tourism indicators, reflecting the gap between "
        "macro-policy language and sub-national measurement infrastructure."
    )

    for i, f in enumerate(findings, 1):
        lines.append(f"{i}. {f}")
    lines.append("")

    lines.append("## Baseline Effect Disclosure\n")
    lines.append(
        "Observed annual growth rates are computed as CAGR over 2020–2025. "
        "This window includes the COVID-19 nadir (2020–2021) as the "
        "baseline, which inflates apparent growth rates during the "
        "2022–2025 recovery period. Commitments classified as `on_track` "
        "on this basis may reflect recovery-driven growth that is not "
        "indicative of sustainable long-term trajectory. Interpret "
        "`on_track` classifications for high-CAGR indicators with this "
        "baseline effect in mind. Future MyTourismSCI versions should use "
        "pre-COVID (2017–2019) trend as the baseline where data "
        "availability allows.\n"
    )

    lines.append("## Mappability as a Finding\n")
    lines.append(
        f"Of {total_commitments} extracted commitments, {len(gap_df)} "
        "could be mapped to observable MyTourismSCI indicators for gap "
        "analysis. The remainder either target metrics not tracked at "
        "state-level in current DOSM publications (employment share by "
        "tourism industry, occupancy rate by state, GDP share from tourism "
        "by state) or are qualitative aspirations without measurable "
        "targets. This gap is itself a finding: current Malaysian tourism "
        "policy commitments frequently use metrics for which state-level "
        "tracking infrastructure does not yet exist, limiting systematic "
        "monitoring. MyTourismSCI's future value increases as DOSM expands "
        "sub-national indicator coverage.\n"
    )
    lines.append(
        "All 4 mappable commitments fall within the Economic sustainability "
        "dimension (visitor arrivals, tourism receipts). No Environmental "
        "or Social commitments in the extraction set map to observable "
        "MyTourismSCI indicators. This means AO3 gap analysis speaks only "
        "to economic sustainability trajectory, not the full three-pillar "
        "composite. Future MyTourismSCI versions expanding sub-national "
        "environmental and social indicator coverage (particularly waste "
        "per capita, tourism-sector wage by state, green-hotel share time "
        "series) would enable multi-dimensional gap analysis.\n"
    )

    lines.append("## Data Limitations\n")
    lines.append(
        "- **Unmappable commitment types:** employment, other (sectoral "
        "growth, GHG reduction, modal share, etc.) lack corresponding "
        "state-level tourism indicators in the current dataset."
    )
    lines.append(
        "- **Unit mismatches:** Commitments expressed as growth rates or "
        "GDP shares require macro-economic denominators not available at "
        "state level."
    )
    lines.append(
        "- **State coverage:** Only 5 of 16 states (plus national) have "
        "extracted policy commitments. States without tourism master plans "
        "in the extraction corpus have zero commitments."
    )
    lines.append(
        "- **Domestic vs. international:** Where commitments reference "
        "total or international arrivals, only domestic visitor data is "
        "available for comparison. KUL international arrivals commitment "
        "(13.0M by 2040) excluded — no state-level international arrivals "
        "data available; state-of-entry ≠ destination per DOSM "
        "methodology guidance."
    )
    lines.append(
        "- **Hotel rooms/occupancy:** The hotel_rooms commitment for "
        "Perlis targets occupancy rate, not room count; no occupancy "
        "indicator exists in the dataset.\n"
    )

    return "\n".join(lines)


def face_validity_check(gap_df: pd.DataFrame) -> None:
    if gap_df.empty:
        log.info("No gap results to validate.")
        return

    log.info("=== FACE VALIDITY CHECK ===")
    off_track = gap_df[gap_df["status"].isin(["off_track", "at_risk"])]
    for _, r in off_track.iterrows():
        prefix = "[REVIEW] " if r["status"] == "off_track" else ""
        log.info(
            "%s%s | %s | target %.1f %s by %d | current %.1f | "
            "CAGR %.3f | status: %s",
            prefix, r["state"], r["commitment_type"],
            r["target_value"], r["target_unit"], r["target_year"],
            r["current_value"],
            r.get("observed_cagr", 0) or 0,
            r["status"],
        )

    already_met = gap_df[gap_df["status"] == "already_met"]
    for _, r in already_met.iterrows():
        log.info(
            "ALREADY MET: %s | %s | target %.1f | current %.1f",
            r["state"], r["commitment_type"],
            r["target_converted"], r["current_value"],
        )

    log.info("=== END VALIDITY CHECK ===")


def main() -> None:
    commitments, scores, indicators = load_inputs()

    # Task 1: Inspect
    inspect_commitments(commitments)

    # Task 2: Filter usable
    usable = filter_usable(commitments)

    # Task 3: Compute gap analysis
    gap_df = compute_gap_analysis(usable, indicators)

    if not gap_df.empty:
        OUTPUTS.mkdir(parents=True, exist_ok=True)
        gap_df.to_parquet(OUTPUTS / "ao3_gap_analysis.parquet", index=False)
        log.info("Saved gap analysis to outputs/ao3_gap_analysis.parquet")

    # Task 6: Face validity
    face_validity_check(gap_df)

    # Task 4: State briefs
    BRIEFS_DIR.mkdir(parents=True, exist_ok=True)
    state_counts = commitments["state"].value_counts().to_dict()
    brief_states = usable["state"].unique().tolist()
    for state in brief_states:
        brief = generate_state_brief(
            state, gap_df, scores, indicators,
            total_extracted_for_state=state_counts.get(state, 0),
        )
        code = state if state != "national" else "national"
        out_path = BRIEFS_DIR / f"{code}.md"
        out_path.write_text(brief, encoding="utf-8")
        log.info("Wrote brief: %s", out_path.name)

    # Task 5: National synthesis
    all_unmappable = list(
        usable[
            ~usable["commitment_type"].isin(COMMITMENT_MAP)
            | usable["commitment_type"].isin(UNMAPPABLE_TYPES)
        ]["commitment_type"].unique()
    )
    synthesis = generate_national_synthesis(
        gap_df, len(commitments), all_unmappable,
    )
    synthesis_path = OUTPUTS / "ao3_national_synthesis.md"
    synthesis_path.write_text(synthesis, encoding="utf-8")
    log.info("Wrote national synthesis: %s", synthesis_path.name)


if __name__ == "__main__":
    main()
