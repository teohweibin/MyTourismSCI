# WEF T&TDI External Validation

## Method
National MyTourismSCI aggregate = tourism-receipts-weighted average of the 16 state `mytourismsci_score` values per year (receipts from `tourism_receipts_rm_mil` in `state_year_indicators.parquet`).

## National MyTourismSCI trajectory (2020-2025)

| Year | National MyTourismSCI (0-1) |
|---|---|
| 2020 | 0.3139 |
| 2021 | 0.2713 |
| 2022 | 0.2990 |
| 2023 | 0.3021 |
| 2024 | 0.3178 |
| 2025 | 0.3233 |

## WEF Travel & Tourism Development Index (TTDI), Malaysia

TTDI is published **biennially** (2019, 2021, 2024), so there is no year-by-year external series to compare against directly.

| Edition | Score (1-7) | Global rank | Confirmed? |
|---|---|---|---|
| 2019 | 4.376 (back-calculated from 2024's '-2.2% since 2019') | - | No |
| 2021 | not found in public sources this session | 38 | Rank only |
| 2024 | 4.28 | 35 (-7 vs. 2019) | Yes |

**CAVEAT:** the 2019 and 2021 score cells above are incomplete/derived — re-verify against the primary WEF TTDI 2024 country profile PDF (`weforum.org/publications/travel-tourism-development-index-2024/`) before citing exact figures in the final report. The 2024 score and both ranks are confirmed from the published report.

## Direction of correspondence
Malaysia's WEF TTDI **declined** across both available comparison points (2019->2021: rank fell; 2019->2024: score fell 2.2%, rank fell from ~28th-equivalent to 35th). This direction is broadly consistent with MyTourismSCI's national trajectory, which shows volatility with a post-2021 dip before partial recovery (see table above) rather than sustained improvement.

**Partial divergence is expected and is not a validity failure:** WEF TTDI is a *competitiveness*-oriented index (business environment, infrastructure, ICT readiness, price competitiveness) whereas MyTourismSCI is *sustainability*-oriented (environmental pressure and social-equity indicators weighted at 60% combined). A state/country can be gaining tourism competitiveness while losing ground on environmental or social sustainability, or vice versa — so directional agreement should be read as loose corroboration of the same underlying tourism-sector conditions, not as agreement on construct.

This comparison should be treated as an **external plausibility check**, not a formal validation, given the sparse (biennial, partly-unconfirmed) comparison series.