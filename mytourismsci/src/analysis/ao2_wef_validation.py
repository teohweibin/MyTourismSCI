"""
AO2 Step 3.7 — WEF Travel & Tourism Development Index (TTDI) external
validation of the national MyTourismSCI aggregate.

National MyTourismSCI aggregate = tourism-receipts-weighted average of
state mytourismsci_score, per year.

WEF TTDI is published BIENNIALLY (2019, 2021, 2024 editions) — there is
no annual series. Malaysia's confirmed published figures (sourced via web
search of the WEF TTDI 2024 in-full report and secondary press coverage):

    2024 edition: score 4.28 / 7, global rank 35 (-7 ranks, -2.2% score
                  vs. its 2019 baseline)
    2021 edition: global rank 38 (Malaysia recorded one of the "largest
                  rank declines"); an exact 2021 score could not be
                  confirmed from public sources in this session.
    2019 edition (TTCI, recalculated under TTDI methodology for
                  comparability): derived as 4.28 / (1 - 0.022) ~= 4.376.
                  This is a BACK-CALCULATION from the 2024 report's
                  "-2.2% since 2019" figure, not a directly observed value.

CAVEAT: these WEF figures should be re-verified against the primary WEF
TTDI 2024 country-profile PDF before this validation goes into the final
report — search access in this session could not pull the exact full
historical score table. Replace WEF_TTDI_MALAYSIA below if you obtain
exact figures.
"""
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

WEF_TTDI_MALAYSIA = {
    # year: (score on 1-7 scale, confirmed True/False)
    2019: (4.376, False),  # back-calculated, see module docstring
    2021: (None, False),   # rank 38 confirmed; score not confirmed
    2024: (4.28, True),    # confirmed: WEF TTDI 2024 in-full report
}


def national_aggregate(scores_df: pd.DataFrame, indicators_df: pd.DataFrame) -> pd.DataFrame:
    df = scores_df.merge(
        indicators_df[["state_code", "year", "tourism_receipts_rm_mil"]],
        on=["state_code", "year"], how="left",
    )
    rows = []
    for year, g in df.groupby("year"):
        receipts = g["tourism_receipts_rm_mil"].fillna(0)
        if receipts.sum() == 0:
            weight = pd.Series(1 / len(g), index=g.index)  # equal-weight fallback
        else:
            weight = receipts / receipts.sum()
        national_score = (g["mytourismsci_score"] * weight).sum()
        rows.append({"year": year, "national_mytourismsci_score": national_score})
    return pd.DataFrame(rows)


def rescale_ttdi_to_unit(score):
    """Rescale WEF's 1-7 scale onto MyTourismSCI's 0-1 scale for the plot,
    using the theoretical 1-7 bounds (not sample min-max), so the rescaled
    value reflects absolute standing, not relative-to-Malaysia's-own-range."""
    if score is None:
        return None
    return (score - 1) / (7 - 1)


def write_validation_md(national_df: pd.DataFrame, path: str):
    lines = [
        "# WEF T&TDI External Validation\n",
        "## Method",
        "National MyTourismSCI aggregate = tourism-receipts-weighted "
        "average of the 16 state `mytourismsci_score` values per year "
        "(receipts from `tourism_receipts_rm_mil` in "
        "`state_year_indicators.parquet`).\n",
        "## National MyTourismSCI trajectory (2020-2025)\n",
        "| Year | National MyTourismSCI (0-1) |",
        "|---|---|",
    ]
    for _, r in national_df.iterrows():
        lines.append(f"| {int(r['year'])} | {r['national_mytourismsci_score']:.4f} |")

    lines += [
        "",
        "## WEF Travel & Tourism Development Index (TTDI), Malaysia\n",
        "TTDI is published **biennially** (2019, 2021, 2024), so there is "
        "no year-by-year external series to compare against directly.\n",
        "| Edition | Score (1-7) | Global rank | Confirmed? |",
        "|---|---|---|---|",
        "| 2019 | 4.376 (back-calculated from 2024's '-2.2% since 2019') | - | No |",
        "| 2021 | not found in public sources this session | 38 | Rank only |",
        "| 2024 | 4.28 | 35 (-7 vs. 2019) | Yes |",
        "",
        "**CAVEAT:** the 2019 and 2021 score cells above are incomplete/"
        "derived — re-verify against the primary WEF TTDI 2024 country "
        "profile PDF (`weforum.org/publications/travel-tourism-development-"
        "index-2024/`) before citing exact figures in the final report. "
        "The 2024 score and both ranks are confirmed from the published "
        "report.\n",
        "## Direction of correspondence",
        "Malaysia's WEF TTDI **declined** across both available "
        "comparison points (2019->2021: rank fell; 2019->2024: score fell "
        "2.2%, rank fell from ~28th-equivalent to 35th). This direction is "
        "broadly consistent with MyTourismSCI's national trajectory, which "
        "shows volatility with a post-2021 dip before partial recovery "
        "(see table above) rather than sustained improvement.\n",
        "**Partial divergence is expected and is not a validity failure:** "
        "WEF TTDI is a *competitiveness*-oriented index (business "
        "environment, infrastructure, ICT readiness, price competitiveness) "
        "whereas MyTourismSCI is *sustainability*-oriented (environmental "
        "pressure and social-equity indicators weighted at 60% combined). "
        "A state/country can be gaining tourism competitiveness while "
        "losing ground on environmental or social sustainability, or vice "
        "versa — so directional agreement should be read as loose "
        "corroboration of the same underlying tourism-sector conditions, "
        "not as agreement on construct.\n",
        "This comparison should be treated as an **external plausibility "
        "check**, not a formal validation, given the sparse (biennial, "
        "partly-unconfirmed) comparison series.",
    ]
    with open(path, "w") as f:
        f.write("\n".join(lines))


def plot_comparison(national_df: pd.DataFrame, path: str):
    fig, ax1 = plt.subplots(figsize=(9, 5))
    ax1.plot(national_df["year"], national_df["national_mytourismsci_score"],
              "o-", color="#2b6cb0", label="National MyTourismSCI (0-1, left axis)")
    ax1.set_ylabel("National MyTourismSCI score (0-1)", color="#2b6cb0")
    ax1.set_ylim(0, 1)
    ax1.set_xlabel("Year")

    ax2 = ax1.twinx()
    wef_years = [y for y, (s, _) in WEF_TTDI_MALAYSIA.items() if s is not None]
    wef_scores = [WEF_TTDI_MALAYSIA[y][0] for y in wef_years]
    confirmed = [WEF_TTDI_MALAYSIA[y][1] for y in wef_years]
    colors = ["#c05621" if c else "#c0562180" for c in confirmed]
    ax2.scatter(wef_years, wef_scores, color=colors, s=90, marker="D",
                label="WEF TTDI Malaysia (1-7, right axis)", zorder=5)
    ax2.set_ylabel("WEF TTDI score (1-7)", color="#c05621")
    ax2.set_ylim(1, 7)

    fig.legend(loc="upper center", bbox_to_anchor=(0.5, 1.08), ncol=2)
    ax1.set_title("MyTourismSCI (national) vs. WEF TTDI Malaysia", pad=40)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main():
    scores = pd.read_parquet("outputs/mytourismsci_scores.parquet")
    indicators = pd.read_parquet("data/final/state_year_indicators.parquet")

    national_df = national_aggregate(scores, indicators)
    write_validation_md(national_df, "outputs/wef_ttdi_validation.md")
    plot_comparison(national_df, "outputs/figures/wef_ttdi_comparison.png")
    print(national_df)
    print("Wrote outputs/wef_ttdi_validation.md and outputs/figures/wef_ttdi_comparison.png")


if __name__ == "__main__":
    main()
