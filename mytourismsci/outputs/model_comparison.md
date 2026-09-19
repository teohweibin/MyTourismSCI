# AO2 Model Comparison

Hold-out protocol: train on target-years 2021-2024 (lag years 2020-2023), test on target-year 2025.

| Model | MAE (2025 hold-out) |
|---|---|
| XGBoost (pooled) | 0.027797 |
| Naive (persistence) | 0.027810 |
| ARIMA (per-state) | 0.031758 |

**Shipped model: XGBoost (pooled)**

## Honesty check: XGBoost vs. naive is nearly a statistical tie
XGBoost beats the naive persistence baseline by only 0.000013 MAE (0.05% relative improvement) on a 16-observation test set. With just 64 training rows and 16 held-out states, this margin is well within noise — it should **not** be read as strong evidence that the indicator features add real predictive power over 'assume next year looks like this year.' XGBoost is still shipped because (a) it is the only one of the three that can produce SHAP-based driver attribution, which is a required AO2 deliverable, and (b) it does not do worse than the naive floor. This caveat should be carried into the report: the driver diagnosis narrative is more defensible than the forecast precision claim.

## Justification
- The naive persistence baseline is included as the floor: it assumes zero year-over-year change and is often surprisingly competitive on a short, noisy composite index.
- ARIMA(1,0,0)/(1,1,0) per state is fit on only 5 training points per state, which is thin for stable AR estimation; several states' forecasts fall back to a naive last-value when the ARIMA fit is numerically degenerate. Reported as a comparison point per spec, not shipped.
- XGBoost pools all 16 states x 4 years (64 obs) and can use the full indicator set plus state fixed effects, at the cost of being a black box (mitigated via SHAP in shap_drivers.parquet).

## Feature leakage guard
The contemporaneous `economic_score`, `environmental_score`, and `social_score` columns were **excluded** from the feature set. These are the exact pillar inputs that AO1's geometric-mean aggregation combines (weights 40/35/25) to produce `mytourismsci_score` in the same year — including them contemporaneously would let the model near-perfectly reconstruct the target rather than genuinely predict it. Only their **lagged** (t-1) versions are used as features.

## Forecast horizon assumption (2026-2028)
`state_year_indicators.parquet` has no rows beyond 2025, so there are no observed exogenous indicators for the forecast years. Recursive forecasts hold each state's 2025 indicator values and 2025 pillar scores constant for 2026-2028, updating only the `mytourismsci_score_lag1` feature with the model's own prior-step forecast. This is a standard last-observation-carried-forward assumption for short-horizon forecasting when exogenous drivers are not separately projected. It means the 2027/2028 forecasts are conditional on 2025 conditions persisting and should be read as a trend continuation, not an update to structural drivers.

## Clipping
Forecasts and CI bounds are clipped to [0, 1] since the composite index is bounded by construction (min-max normalization + geometric mean of bounded inputs).