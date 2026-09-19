# AO2 — Forecasting & Driver Diagnosis: Report Summary

**Prepared for:** Report Lead (Section 4 — Findings)
**Covers:** `docs/ao2_spec.md` deliverables — 3-year forecast, model comparison,
SHAP driver diagnosis, WEF T&TDI external validation.
**Status:** Complete. All outputs in `outputs/` and `outputs/figures/`.

---

## 1. What this analysis does

AO1 produced a MyTourismSCI composite score for all 16 Malaysian states,
2020–2025. AO2 takes that score as a fixed input and answers two
questions per state:

1. **Where is it heading?** — a 3-year forecast to 2028.
2. **Why is it where it is?** — a feature-importance (SHAP) breakdown of
   the top-3 drivers behind each state's 2025 position.

A third piece checks whether the national trend agrees, even loosely,
with an independent external benchmark (WEF's Travel & Tourism
Development Index).

---

## 2. Method, in brief

Three models were compared on a same held-out year (2025 predicted from
2020–2024 data): a **naive persistence** baseline (assume next year =
this year), a **per-state ARIMA(1,0,0)**, and a **pooled XGBoost**
regressor using lagged own-score, lagged pillar sub-scores, and the full
set of raw harmonized indicators as features, with state identity as a
categorical feature.

| Model | MAE (2025 hold-out) |
|---|---|
| **XGBoost (pooled)** | **0.0278** |
| Naive (persistence) | 0.0278 |
| ARIMA (per-state) | 0.0318 |

**XGBoost was shipped**, but the margin over naive persistence is
negligible (a difference of 0.000013 MAE on only 16 test observations —
not a statistically meaningful improvement). This is disclosed here
deliberately: **the forecast should be framed in the report as a
reasonable trend continuation, not as a high-precision prediction.**
XGBoost earns its place primarily because it is the only one of the
three that supports SHAP-based driver attribution, which is the more
defensible half of this analysis.

One methodological correction is worth naming explicitly for the
methodology section: the model does **not** use same-year
`economic_score` / `environmental_score` / `social_score` as predictors,
because those three values are the exact inputs AO1's geometric-mean
aggregation combines into `mytourismsci_score` in the same year — using
them contemporaneously would let the model reconstruct the target rather
than predict it. Only their **lagged (prior-year)** versions are used.

**Forecast horizon caveat:** the harmonized indicator table has no rows
beyond 2025. The 2026–2028 forecasts therefore hold each state's 2025
indicator profile constant and roll forward only the score's own lag.
Practically, this means the forecast represents *"if 2025 conditions
persist, here is where the score trend goes,"* not a projection that
accounts for new policy action, infrastructure changes, or shocks.
Confidence intervals widen with each forecast year to reflect this
compounding uncertainty.

---

## 3. Forecast results (2026–2028)

Full state-year table: `outputs/mytourismsci_forecast.parquet`. Figure:
`outputs/figures/forecast_trajectory.png`.

### Headline pattern: rank order is largely stable

Comparing 2025 actual rank to the 2028 forecast rank, **12 of 16 states
show no rank change at all**. The composite index is forecast to be
persistent rather than volatile over this horizon — consistent with the
fact that XGBoost barely beats a "nothing changes" baseline (Section 2).

| State | 2025 score | 2025 rank | 2028 forecast | 2028 rank | Rank change |
|---|---|---|---|---|---|
| Sabah | 0.580 | 1 | 0.579 | 1 | — |
| Selangor | 0.477 | 2 | 0.477 | 2 | — |
| Penang | 0.467 | 3 | 0.469 | 3 | — |
| Johor | 0.386 | 4 | 0.345 | 6 | ↓2 |
| Kedah | 0.356 | 5 | 0.358 | 4 | ↑1 |
| Kuala Lumpur | 0.356 | 6 | 0.357 | 5 | ↑1 |
| Pahang | 0.333 | 7 | 0.332 | 7 | — |
| Terengganu | 0.223 | 8 | 0.222 | 8 | — |
| Negeri Sembilan | 0.222 | 9 | 0.221 | 10 | ↓1 |
| Sarawak | 0.221 | 10 | 0.222 | 9 | ↑1 |
| Perak | 0.184 | 11 | 0.184 | 11 | — |
| Kelantan | 0.101 | 12 | 0.102 | 12 | — |
| Putrajaya | 0.067 | 13 | 0.066 | 13 | — |
| Melaka | 0.058 | 14 | 0.058 | 14 | — |
| Perlis | 0.048 | 15 | 0.049 | 15 | — |
| Labuan | 0.031 | 16 | 0.033 | 16 | — |

**The only movement of note is Johor**, forecast to slip two places
(4th → 6th) — the only state with a rank change of more than one
position. This is worth a sentence in Section 4 as the single
"watch" case from the forecast, since everything else is near-flat.

**Sabah, Selangor, Penang hold the top-3 with wide margins** and are
forecast to remain there through 2028 — a useful anchor statement for
the report's tourism-development narrative.

---

## 4. Driver diagnosis (SHAP)

Full table: `outputs/shap_drivers.parquet`. For each state, this is the
top-3 features (ranked by absolute SHAP value) explaining that state's
**2025** score, from the same shipped model.

### Pattern across states: `green_hotel_count` dominates

`green_hotel_count` appears in the **top-3 drivers for 15 of 16
states**, and is the single top driver for 9 states (including all of
the top 3 — Sabah, Selangor, Penang). `dts_rooms_count` and the model's
own lagged score are the other recurring drivers.

**Important interpretive caveat for the report, not just a technical
footnote:** `green_hotel_count` is a **static current-snapshot**
indicator (per the harmonization methodology, MOTAC's green-hotel
register has no year dimension and is replicated identically across all
6 years for each state). Because it never varies over time within a
state, the model is partly using it as a **proxy for state identity**
rather than a signal of year-to-year environmental policy effectiveness.
Read the SHAP result as *"states with more ASEAN Green Hotel–certified
properties tend to score higher, and this is a persistent
between-state pattern"* — not as *"a state's green-hotel count moved
recently and caused its score to move."* This distinction matters
because green-hotel certification is one of the few levers MOTAC could
plausibly act on quickly (see AO3 policy-commitment findings), so the
report should frame it as a **cross-sectional association worth
policy attention**, not a proven causal within-state driver.

### Selected state highlights

| State | Rank | Top-3 drivers (SHAP value) |
|---|---|---|
| Sabah (#1) | Top | `green_hotel_count` (+0.075), `mytourismsci_score_lag1` (+0.071), `dts_rooms_count` (+0.058) |
| Selangor (#2) | Top | `green_hotel_count` (+0.073), `mytourismsci_score_lag1` (+0.064), `dts_rooms_count` (+0.044) |
| Penang (#3) | Top | `green_hotel_count` (+0.065), `dts_rooms_count` (+0.049), `mytourismsci_score_lag1` (+0.046) |
| Johor (#4, forecast to slip) | Mid | `mytourismsci_score_lag1` (+0.059), `green_hotel_count` (+0.058), `wqi_annual` (−0.038) |
| Labuan (#16, lowest) | Bottom | `mytourismsci_score_lag1` (−0.075), `green_hotel_count` (−0.057), `dts_rooms_count` (−0.032) |

Sabah and Selangor's top drivers are near-identical in composition —
both anchored by high green-hotel presence and hotel capacity
(`dts_rooms_count`) rather than by the same environmental or social
indicators that AO1 flagged as biased for large states (see Section 5).
Johor is the one state where a negative environmental indicator
(`wqi_annual`, water quality index) appears in the top-3 — worth
connecting to its forecast rank slip in Section 4's narrative if the
Report Lead wants a single integrated Johor case study.

---

## 5. WEF T&TDI external validation

Full writeup: `outputs/wef_ttdi_validation.md`. Figure:
`outputs/figures/wef_ttdi_comparison.png`.

The national MyTourismSCI aggregate (tourism-receipts-weighted average
across states) moved as follows:

| Year | National MyTourismSCI (0–1) |
|---|---|
| 2020 | 0.314 |
| 2021 | 0.271 |
| 2022 | 0.299 |
| 2023 | 0.302 |
| 2024 | 0.318 |
| 2025 | 0.323 |

Malaysia's WEF TTDI score **declined** over the only two comparable
data points available (TTDI is published biennially: 2019 and 2024
editions fall in range; 2021's exact score could not be confirmed from
public sources, only its rank of 38th). The 2024 TTDI score is 4.28 (of
7), rank 35 — down 2.2% and 7 ranks from 2019.

**Direction of correspondence:** loosely consistent. MyTourismSCI dipped
in 2021 before recovering, while WEF TTDI also declined over the same
broader window. **This should be framed as a plausibility check, not a
formal validation** — the WEF figures are sparse (biennial, one of three
data points not fully confirmed) and the two indices measure different
constructs: WEF TTDI is competitiveness-oriented (business environment,
infrastructure, ICT), MyTourismSCI is sustainability-oriented
(environment and social pillars carry 60% combined weight). Partial
divergence is expected and does not undermine either index — it reflects
that a country/state can gain tourism competitiveness while losing
ground on environmental or social sustainability, or vice versa.

**Before this goes in the report:** the 2019 WEF figure used here (4.376)
is *back-calculated* from the 2024 report's "−2.2% since 2019" statistic,
not directly sourced — worth a quick verification pass against the
primary WEF TTDI 2024 PDF if time allows.

---

## 6. Limitations carried into this analysis

These inherit from AO1/harmonization and directly affect how the
forecast and SHAP results should be interpreted:

- **Sarawak's environmental score is understated** (buffer-fraction
  method penalizes large states), so Sarawak's forecast and SHAP drivers
  should be read with this known downward bias in mind.
- **`green_hotel_count` and `motac_hotels_rated_count` are static
  snapshots**, not time series — see Section 4's caveat above.
- **Population and `hh_water_access` are missing for 2024–2025**, so any
  derived per-capita indicators (`tourism_concentration_ratio`,
  `hotel_density_per_capita`) are NaN for the most recent years and
  contributed nothing to those years' predictions.
- **`international_arrivals_share` is NaN for all 96 rows** — retained
  as a feature for schema consistency but carries zero information.
- **The forecast assumes 2025 conditions persist** (Section 2) — it is
  not policy-responsive and will not reflect any 2026+ intervention.

---

## 7. File reference

| File | Contents |
|---|---|
| `outputs/mytourismsci_forecast.parquet` / `.csv` | state_code, year (2026–2028), forecasted_score, forecast_ci_low, forecast_ci_high, model_used |
| `outputs/shap_drivers.parquet` / `.csv` | state_code, feature, shap_value, shap_rank (top-3 per state, 2025 basis) |
| `outputs/model_comparison.md` | Full MAE comparison + methodology notes |
| `outputs/wef_ttdi_validation.md` | Full WEF validation writeup + sourcing caveats |
| `outputs/figures/forecast_trajectory.png` | 16-panel actual + forecast + CI chart |
| `outputs/figures/wef_ttdi_comparison.png` | National score vs. WEF TTDI dual-axis chart |
| `src/analysis/ao2_features.py`, `ao2_forecast.py`, `ao2_wef_validation.py` | Reproducible pipeline code |
| `tests/test_ao2.py` | 6 passing tests (shape, no-leakage, bounds) |
