"""AO1: Construct and validate MyTourismSCI composite index.

Methodology: OECD/JRC (2008) Handbook on Constructing Composite Indicators,
UNDP HDI geometric mean aggregation (2010 revision), OPHI MPI sub-national
composite methodology (as adopted by DOSM for Malaysia).
Pillar structure aligned to UN Tourism MST framework.

Inputs:  data/final/state_year_indicators.parquet
Outputs: outputs/mytourismsci_scores.parquet
         outputs/pillar_pca_validation.md
         outputs/monte_carlo_sensitivity.parquet
         outputs/monte_carlo_summary.md
         outputs/figures/composite_heatmap_2025.png
         outputs/figures/rank_trajectory_2020_2025.png
Dependencies: pandas, numpy, scikit-learn, matplotlib
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

DATA_FINAL = PROJECT_ROOT / "data" / "final"
OUTPUTS = PROJECT_ROOT / "outputs"
FIGURES = OUTPUTS / "figures"

TARGET_YEARS = list(range(2020, 2026))
MISSING_THRESHOLD = 0.30

# ── Indicator configuration ──────────────────────────────────────────────
# direction: 1 = higher-is-better, -1 = lower-is-better
INDICATOR_CONFIG: dict[str, dict] = {
    "tourism_receipts_rm_mil": {"pillar": "Economic", "direction": 1},
    "expenditure_per_visitor":  {"pillar": "Economic", "direction": 1},
    "alos_nights":              {"pillar": "Economic", "direction": 1},
    "wqi_annual":               {"pillar": "Environmental", "direction": 1},
    "green_hotel_share":        {"pillar": "Environmental", "direction": 1},
    "coastal_area_fraction":    {"pillar": "Environmental", "direction": 1},
    "pa_area_fraction":         {"pillar": "Environmental", "direction": 1},
    "hh_water_access":          {"pillar": "Social", "direction": 1},
    "domestic_visitors_000":    {"pillar": "Social", "direction": 1},
    "motac_hotels_rated_count": {"pillar": "Social", "direction": 1},
    # Dropped candidates (documented for transparency):
    # tourism_concentration_ratio: 33.3% missing (>30%) — overtourism proxy
    # waste_tonnes: 92.7% missing — insufficient state-year coverage
    # international_arrivals_share: 100% missing — national-only source
    # hotel_density_per_capita: 33.3% missing — derived from population
}

PILLAR_WEIGHTS = {"Economic": 0.40, "Environmental": 0.35, "Social": 0.25}
PILLARS = list(PILLAR_WEIGHTS.keys())
EPSILON = 0.001
MC_DRAWS = 1000
MC_SEED = 42
DIRICHLET_CONCENTRATION = 20


# ── Task 1: Preprocessing (OECD/JRC Ch. 3) ──────────────────────────────

def preprocess(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Handle missing data and outliers per OECD/JRC (2008) Chapter 3.

    Missing-data strategy: indicators with >30% missing cells are excluded.
    Remaining gaps are imputed with within-state mean (OECD/JRC §3.3,
    'available case' approach preserving cross-sectional structure).

    Outlier treatment: within-year IQR detection; values beyond 1st/99th
    percentile are winsorized (OECD/JRC §3.2, winsorization preferred over
    trimming to retain sample size).
    """
    all_indicators = list(INDICATOR_CONFIG.keys())
    available = [c for c in all_indicators if c in df.columns]
    for col in available:
        df[col] = df[col].astype(float)

    kept, dropped = [], []
    for ind in available:
        miss_pct = df[ind].isna().sum() / len(df)
        if miss_pct > MISSING_THRESHOLD:
            log.warning(
                "DROPPED indicator %s: %.1f%% missing (threshold %.0f%%)",
                ind, miss_pct * 100, MISSING_THRESHOLD * 100,
            )
            dropped.append(ind)
        else:
            kept.append(ind)
            if miss_pct > 0:
                imputed_count = 0
                for state in df["state_code"].unique():
                    mask = (df["state_code"] == state) & df[ind].isna()
                    if mask.any():
                        state_mean = df.loc[df["state_code"] == state, ind].mean()
                        if pd.notna(state_mean):
                            df.loc[mask, ind] = state_mean
                            imputed_count += mask.sum()
                        else:
                            global_mean = df[ind].mean()
                            df.loc[mask, ind] = global_mean
                            imputed_count += mask.sum()
                log.info("Imputed %d cells for %s (state-mean)", imputed_count, ind)

    for ind in kept:
        for year in TARGET_YEARS:
            mask_year = df["year"] == year
            vals = df.loc[mask_year, ind]
            if vals.notna().sum() < 4:
                continue
            p01, p99 = vals.quantile(0.01), vals.quantile(0.99)
            low_mask = mask_year & (df[ind] < p01)
            high_mask = mask_year & (df[ind] > p99)
            n_winsorized = low_mask.sum() + high_mask.sum()
            if n_winsorized > 0:
                df.loc[low_mask, ind] = p01
                df.loc[high_mask, ind] = p99
                log.info("Winsorized %d values for %s in %d", n_winsorized, ind, year)

    return df, kept, dropped


# ── Task 2: Direction alignment (OECD/JRC Ch. 3) ────────────────────────

def align_direction(df: pd.DataFrame, indicators: list[str]) -> pd.DataFrame:
    """Flip lower-is-better indicators so all point in the same direction.

    Per OECD/JRC (2008) §3.1: 'If an increase in the indicator corresponds
    to a decrease in the phenomenon, the indicator is reversed.' Uses
    max-flip: flipped = max(year) - value, preserving scale.
    """
    for ind in indicators:
        cfg = INDICATOR_CONFIG[ind]
        if cfg["direction"] == -1:
            for year in TARGET_YEARS:
                mask = df["year"] == year
                max_val = df.loc[mask, ind].max()
                df.loc[mask, ind] = max_val - df.loc[mask, ind]
            log.info("Flipped (lower-is-better): %s", ind)
    return df


# ── Task 3: Normalization (OECD/JRC Ch. 3) ──────────────────────────────

def normalize_minmax(df: pd.DataFrame, indicators: list[str]) -> pd.DataFrame:
    """Min-max normalization within year to [0, 1].

    Per OECD/JRC (2008) §3.4: min-max recommended for relative-comparison
    applications where absolute magnitude is less important than
    cross-sectional ranking within a reference period.
    """
    for ind in indicators:
        col_norm = f"{ind}_norm"
        df[col_norm] = np.nan
        for year in TARGET_YEARS:
            mask = df["year"] == year
            vals = df.loc[mask, ind]
            vmin, vmax = vals.min(), vals.max()
            if vmax - vmin > 0:
                df.loc[mask, col_norm] = (vals - vmin) / (vmax - vmin)
            else:
                df.loc[mask, col_norm] = 0.5
    return df


# ── Task 4: Pillar aggregation (OECD/JRC Ch. 5, UNDP HDI) ───────────────

def aggregate_pillars(df: pd.DataFrame, indicators: list[str]) -> pd.DataFrame:
    """Geometric mean within each pillar.

    Per UNDP (2010) HDI Technical Note: geometric mean penalises imbalance
    across sub-dimensions — a state cannot compensate for poor environmental
    performance with strong economic performance within a pillar.

    Epsilon (0.001) added before log to handle exact zeros, following
    OECD/JRC (2008) §5.2 recommendation for bounded indicators.
    """
    pillar_indicators: dict[str, list[str]] = {p: [] for p in PILLARS}
    for ind in indicators:
        pillar = INDICATOR_CONFIG[ind]["pillar"]
        pillar_indicators[pillar].append(f"{ind}_norm")

    for pillar, cols in pillar_indicators.items():
        score_col = f"{pillar.lower()}_score"
        if not cols:
            df[score_col] = np.nan
            continue
        sub = df[cols].copy()
        sub = sub + EPSILON
        log_vals = np.log(sub)
        df[score_col] = np.exp(log_vals.mean(axis=1))
        df[score_col] = df[score_col] - EPSILON
        df[score_col] = df[score_col].clip(0, 1)
        log.info("Pillar %s: %d indicators %s", pillar, len(cols), cols)
    return df


# ── Task 5: Composite aggregation ───────────────────────────────────────

def compute_composite(df: pd.DataFrame, weights: dict[str, float] | None = None) -> pd.DataFrame:
    """Weighted geometric mean across pillars.

    Per UNDP HDI (2010): composite = product(pillar_score^weight).
    Default weights: Economic 0.40, Environmental 0.35, Social 0.25
    (project design reflecting Malaysia's RMK13 priorities).
    """
    if weights is None:
        weights = PILLAR_WEIGHTS
    score_cols = {p: f"{p.lower()}_score" for p in PILLARS}

    log_composite = np.zeros(len(df))
    for pillar, col in score_cols.items():
        w = weights[pillar]
        log_composite += w * np.log(df[col].clip(EPSILON))

    df["mytourismsci_score"] = np.exp(log_composite)
    df["mytourismsci_score"] = df["mytourismsci_score"].clip(0, 1)

    df["rank"] = (
        df.groupby("year")["mytourismsci_score"]
        .rank(ascending=False, method="min")
        .astype(int)
    )
    return df


# ── Task 6: PCA validation (OECD/JRC Ch. 2) ─────────────────────────────

def pca_validation(df: pd.DataFrame, indicators: list[str]) -> str:
    """PCA within each pillar to assess internal coherence.

    Per OECD/JRC (2008) §2.3: first principal component should explain
    ≥40% of variance for adequate unidimensionality. Below 40% indicates
    weak coherence — indicators may not share a latent construct.
    """
    pillar_indicators: dict[str, list[str]] = {p: [] for p in PILLARS}
    for ind in indicators:
        pillar = INDICATOR_CONFIG[ind]["pillar"]
        pillar_indicators[pillar].append(ind)

    lines = [
        "# PCA Validation of Within-Pillar Coherence",
        "",
        "Reference: OECD/JRC (2008) Handbook, Chapter 2 — Theoretical Framework",
        "Threshold: first PC should explain >= 40% variance for adequate coherence.",
        "",
    ]

    flags = []
    for pillar, inds in pillar_indicators.items():
        lines.append(f"## {pillar} Pillar ({len(inds)} indicators)")
        lines.append("")
        if len(inds) < 2:
            lines.append("Skipped: fewer than 2 indicators for PCA.")
            lines.append("")
            continue

        for year in TARGET_YEARS:
            mask = df["year"] == year
            sub = df.loc[mask, inds].dropna()
            if len(sub) < max(3, len(inds)):
                lines.append(f"### {year}: insufficient non-null observations")
                lines.append("")
                continue

            scaler = StandardScaler()
            X = scaler.fit_transform(sub)
            pca = PCA()
            pca.fit(X)

            var_explained = pca.explained_variance_ratio_
            pc1_var = var_explained[0]
            lines.append(f"### {year}")
            lines.append("")
            lines.append(f"First PC variance explained: **{pc1_var:.1%}**")
            if pc1_var < 0.40:
                flag_msg = f"{pillar} {year}: PC1 = {pc1_var:.1%} < 40%"
                flags.append(flag_msg)
                lines.append(f"**FLAG: Below 40% threshold** — weak coherence")
            lines.append("")
            lines.append("| Indicator | PC1 Loading |")
            lines.append("|---|---|")
            loadings = pca.components_[0]
            for i, ind in enumerate(inds):
                lines.append(f"| {ind} | {loadings[i]:+.3f} |")
            lines.append("")

    if flags:
        lines.append("## Flagged Pillars")
        lines.append("")
        for f in flags:
            lines.append(f"- {f}")
    else:
        lines.append("## Summary")
        lines.append("")
        lines.append("All pillars meet the 40% first-PC variance threshold across all years.")

    return "\n".join(lines)


# ── Task 7: Monte Carlo weight sensitivity (OECD/JRC Ch. 6) ─────────────

def monte_carlo_sensitivity(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Monte Carlo robustness analysis of weight specification.

    Per OECD/JRC (2008) §6.3: Dirichlet-distributed weight draws test
    whether state rankings are sensitive to the assumed weight vector.
    Concentration parameter controls spread around base weights.

    Returns (full_simulations, summary_per_state_year).
    """
    rng = np.random.default_rng(MC_SEED)
    base = np.array([PILLAR_WEIGHTS[p] for p in PILLARS])
    alpha = base * DIRICHLET_CONCENTRATION
    weight_draws = rng.dirichlet(alpha, size=MC_DRAWS)

    score_cols = [f"{p.lower()}_score" for p in PILLARS]
    pillar_vals = df[score_cols].values.clip(EPSILON)
    log_pillars = np.log(pillar_vals)

    all_sims = []
    for i in range(MC_DRAWS):
        w = weight_draws[i]
        log_comp = log_pillars @ w
        comp = np.exp(log_comp).clip(0, 1)
        sim_df = df[["state_code", "year"]].copy()
        sim_df["sim_id"] = i
        sim_df["mytourismsci_score"] = comp
        sim_df["rank"] = (
            sim_df.groupby("year")["mytourismsci_score"]
            .rank(ascending=False, method="min")
            .astype(int)
        )
        all_sims.append(sim_df)

    full = pd.concat(all_sims, ignore_index=True)

    summary_rows = []
    for (state, year), grp in full.groupby(["state_code", "year"]):
        ranks = grp["rank"]
        median_rank = ranks.median()
        r5 = ranks.quantile(0.05)
        r95 = ranks.quantile(0.95)
        stable = ((ranks >= median_rank - 3) & (ranks <= median_rank + 3)).mean()
        summary_rows.append({
            "state_code": state,
            "year": year,
            "median_rank": median_rank,
            "rank_5th": r5,
            "rank_95th": r95,
            "rank_stability": stable,
        })

    summary = pd.DataFrame(summary_rows)
    return full, summary


def monte_carlo_report(summary: pd.DataFrame) -> str:
    lines = [
        "# Monte Carlo Weight Sensitivity Report",
        "",
        f"Draws: {MC_DRAWS} | Dirichlet concentration: {DIRICHLET_CONCENTRATION}",
        f"Base weights: Economic={PILLAR_WEIGHTS['Economic']:.0%}, "
        f"Environmental={PILLAR_WEIGHTS['Environmental']:.0%}, "
        f"Social={PILLAR_WEIGHTS['Social']:.0%}",
        "",
        "## Rank Stability by State (2025)",
        "",
        "| State | Median Rank | 5th pct | 95th pct | Stability |",
        "|---|---|---|---|---|",
    ]

    latest = summary[summary["year"] == 2025].sort_values("median_rank")
    for _, row in latest.iterrows():
        flag = " **SENSITIVE**" if row["rank_stability"] < 0.80 else ""
        lines.append(
            f"| {row['state_code']} | {row['median_rank']:.0f} | "
            f"{row['rank_5th']:.0f} | {row['rank_95th']:.0f} | "
            f"{row['rank_stability']:.0%}{flag} |"
        )

    sensitive = latest[latest["rank_stability"] < 0.80]
    lines.append("")
    if len(sensitive) > 0:
        lines.append(f"## Sensitive States ({len(sensitive)})")
        lines.append("")
        lines.append("The following states have rank stability < 80%, meaning "
                      "their ranking is sensitive to the choice of pillar weights:")
        lines.append("")
        for _, row in sensitive.iterrows():
            lines.append(f"- **{row['state_code']}**: median rank {row['median_rank']:.0f}, "
                          f"range [{row['rank_5th']:.0f}–{row['rank_95th']:.0f}]")
    else:
        lines.append("All states have rank stability >= 80%. Rankings are robust "
                      "to moderate perturbation of pillar weights.")

    return "\n".join(lines)


# ── Task 8: Figures ──────────────────────────────────────────────────────

def plot_heatmap_2025(df: pd.DataFrame) -> Path:
    """State x pillar heatmap for latest year."""
    latest = df[df["year"] == 2025].sort_values("mytourismsci_score", ascending=False)
    states = latest["state_code"].values
    pillar_cols = ["economic_score", "environmental_score", "social_score"]
    data = latest[pillar_cols].values

    fig, ax = plt.subplots(figsize=(8, 10))
    im = ax.imshow(data, cmap="YlGn", aspect="auto", vmin=0, vmax=1)
    ax.set_xticks(range(len(pillar_cols)))
    ax.set_xticklabels(["Economic", "Environmental", "Social"], fontsize=11)
    ax.set_yticks(range(len(states)))
    ax.set_yticklabels(states, fontsize=10)

    for i in range(len(states)):
        for j in range(len(pillar_cols)):
            val = data[i, j]
            color = "white" if val > 0.6 else "black"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                    fontsize=9, color=color)

    ax.set_title("MyTourismSCI Pillar Scores by State (2025)", fontsize=13, pad=12)
    fig.colorbar(im, ax=ax, shrink=0.6, label="Pillar Score [0–1]")
    plt.tight_layout()

    path = FIGURES / "composite_heatmap_2025.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_rank_trajectory(df: pd.DataFrame) -> Path:
    """Line chart of each state's rank over 6 years."""
    fig, ax = plt.subplots(figsize=(12, 8))
    states = sorted(df["state_code"].unique())

    cmap = plt.cm.tab20
    for i, state in enumerate(states):
        sdf = df[df["state_code"] == state].sort_values("year")
        ax.plot(sdf["year"], sdf["rank"], marker="o", markersize=4,
                label=state, color=cmap(i / len(states)), linewidth=1.5)

    ax.set_xlabel("Year", fontsize=12)
    ax.set_ylabel("Rank (1 = best)", fontsize=12)
    ax.set_title("MyTourismSCI State Rankings 2020–2025", fontsize=13)
    ax.invert_yaxis()
    ax.set_yticks(range(1, 17))
    ax.set_xticks(TARGET_YEARS)
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8, ncol=1)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    path = FIGURES / "rank_trajectory_2020_2025.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


# ── Task 9: Face validity ───────────────────────────────────────────────

def face_validity_check(df: pd.DataFrame) -> str:
    latest = df[df["year"] == 2025].sort_values("rank")
    lines = ["", "=== FACE VALIDITY CHECK (2025) ===", ""]

    lines.append("TOP 5:")
    for _, row in latest.head(5).iterrows():
        lines.append(
            f"  {row['rank']:>2}. {row['state_code']}  score={row['mytourismsci_score']:.4f}  "
            f"E={row['economic_score']:.3f} Env={row['environmental_score']:.3f} S={row['social_score']:.3f}"
        )

    lines.append("")
    lines.append("BOTTOM 5:")
    for _, row in latest.tail(5).iterrows():
        lines.append(
            f"  {row['rank']:>2}. {row['state_code']}  score={row['mytourismsci_score']:.4f}  "
            f"E={row['economic_score']:.3f} Env={row['environmental_score']:.3f} S={row['social_score']:.3f}"
        )

    lines.append("")
    eco_top = latest.nsmallest(3, "rank")["state_code"].tolist()
    env_top = latest.nlargest(3, "environmental_score")["state_code"].tolist()

    flags = []
    if "SWK" not in eco_top[:5] and "SBH" not in eco_top[:5]:
        if "SWK" in env_top or "SBH" in env_top:
            pass
        else:
            flags.append(
                "Neither Sarawak nor Sabah in top 5 overall or top 3 environmental "
                "— review environmental pillar weights or indicator selection"
            )

    kul_row = latest[latest["state_code"] == "KUL"]
    if not kul_row.empty:
        kul_env = kul_row["environmental_score"].iloc[0]
        if kul_env > 0.7:
            flags.append(
                f"KUL environmental score ({kul_env:.3f}) seems high for an urban FT "
                "— verify coastal/PA fraction makes sense for KL"
            )

    if flags:
        lines.append("RED FLAGS:")
        for f in flags:
            lines.append(f"  ! {f}")
    else:
        lines.append("No red flags detected — results are directionally plausible.")

    return "\n".join(lines)


# ── Main pipeline ────────────────────────────────────────────────────────

def run_ao1() -> pd.DataFrame:
    """Execute the full AO1 composite index pipeline."""
    df = pd.read_parquet(DATA_FINAL / "state_year_indicators.parquet")
    log.info("Loaded input: %s", df.shape)

    # Task 1: Preprocess
    df, kept_indicators, dropped = preprocess(df)
    log.info("Kept %d indicators, dropped %d", len(kept_indicators), len(dropped))

    # Task 2: Direction alignment
    df = align_direction(df, kept_indicators)

    # Task 3: Normalize
    df = normalize_minmax(df, kept_indicators)

    # Task 4: Pillar aggregation
    df = aggregate_pillars(df, kept_indicators)

    # Task 5: Composite score
    df = compute_composite(df)

    return df, kept_indicators


def main() -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    df, kept_indicators = run_ao1()

    # Checkpoint: pillar sub-scores 2025
    print("\n=== PILLAR SUB-SCORES (2025) ===")
    latest = df[df["year"] == 2025][
        ["state_code", "economic_score", "environmental_score", "social_score",
         "mytourismsci_score", "rank"]
    ].sort_values("rank")
    print(latest.to_string(index=False))

    # Task 6: PCA validation
    pca_report = pca_validation(df, kept_indicators)
    pca_path = OUTPUTS / "pillar_pca_validation.md"
    pca_path.write_text(pca_report, encoding="utf-8")
    log.info("Written: %s", pca_path)
    print("\n" + pca_report)

    # Task 7: Monte Carlo
    mc_full, mc_summary = monte_carlo_sensitivity(df)
    mc_full.to_parquet(OUTPUTS / "monte_carlo_sensitivity.parquet", index=False)
    log.info("Written: monte_carlo_sensitivity.parquet")

    mc_report = monte_carlo_report(mc_summary)
    (OUTPUTS / "monte_carlo_summary.md").write_text(mc_report, encoding="utf-8")
    log.info("Written: monte_carlo_summary.md")
    print("\n" + mc_report)

    # Merge MC summary into main scores
    scores = df[
        ["state_code", "year", "economic_score", "environmental_score",
         "social_score", "mytourismsci_score", "rank"]
    ].merge(mc_summary, on=["state_code", "year"], how="left")
    scores.to_parquet(OUTPUTS / "mytourismsci_scores.parquet", index=False)
    log.info("Written: mytourismsci_scores.parquet")

    # Task 8: Figures
    plot_heatmap_2025(df)
    log.info("Written: composite_heatmap_2025.png")
    plot_rank_trajectory(df)
    log.info("Written: rank_trajectory_2020_2025.png")

    # Task 9: Face validity
    validity = face_validity_check(df)
    print(validity)


if __name__ == "__main__":
    main()
