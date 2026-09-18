# AO2: Forecasting + Driver Diagnosis — Full Execution Spec

> **UPDATE 2026-09-19 01:20 MYT:** AO3 policy commitment gap analysis is
> now COMPLETE (commit `074d52f`). Stats/ML lead does NOT need to do AO3 —
> focus only on the AO2 forecast + SHAP + WEF T&TDI validation tasks
> described below. Read `outputs/ao3_national_synthesis.md` for context on
> how AO3 findings will integrate with AO2 findings in the final report.

**Intended reader:** the Stats/ML teammate executing AO2 over the weekend.
**Prepared by:** [your name]
**Handoff date:** 2026-09-18
**Deadline sensitivity:** all outputs must be committed to `main` by Monday 22 Sep, 6:00 PM MYT to give the Report Lead 23 hours to integrate into the final report before Tuesday 5:00 PM MYT submission.

---

## 1. What has been done (so you know where to plug in)

The data pipeline is complete. AO1 (composite index construction) is complete. Below is what already exists on `main`:

**Ingestion complete (Sessions 1–5C, 6):**
- DOSM Domestic Tourism Survey by state (2020–2025, all 16 states) → `data/processed/dts/`
- DOSM Tourism Satellite Account (national context) → `data/processed/tsa/`
- OpenDOSM API pulls: population, water pollution basins, household amenities access, arrivals by state of entry → `data/processed/opendosm/`
- MOTAC scraped registries: 5,550 registered hotels, 757 rated hotels, 27 green-certified hotels, 27 ASEAN Green Hotel awardees → `data/raw/motac/` and `data/processed/motac/`
- DOE Water Quality Index by state (2014–2025, 182 records) → `data/processed/pdf_tables/doe_wqi_by_state_year.parquet`
- SWCorp waste by state (2022, 7 federalized states only) → `data/processed/pdf_tables/swcorp_waste_by_state.parquet`
- Geospatial layers: WDPA (485 polygons), DOSM state + district boundaries, OSM extract → `data/raw/geospatial/`
- Geospatial state indicators: coastal buffer fraction, PA buffer fraction, estimated coastal/PA hotel exposure per state → `data/processed/geospatial/state_geospatial_indicators.parquet`

**AO3 policy commitment extraction complete (Session 5C):**
- 51 quantitative policy commitments extracted from 10 policy PDFs (RMK13 full + executive summary, MOTAC Annual Report 2024, Johor, Sarawak, KL, Perlis, Malaysia national, Penang, Melaka master plans)
- Coverage: national (17 commitments), KUL (10), JOH (9), SWK (9), PLS (6)
- Output: `data/processed/policy_commitments.parquet` — schema in `config/policy_commitment_schema.json`

**Harmonization complete (Session 7):**
- All indicators merged into `data/final/state_year_indicators.parquet` — 96 rows (16 states × 6 years, 2020–2025), 25 columns
- Long format also available: `data/final/state_year_indicators_long.parquet`
- Methodology: `docs/harmonization_methodology.md`

**AO1 composite index complete (post-Session 7):**
- MyTourismSCI scores computed for 16 states × 6 years using min-max normalization + geometric mean aggregation + Monte Carlo weight sensitivity
- Pillar weights: Economic 40%, Environmental 35%, Social 25%
- All 16 states have rank stability ≥ 98% under Dirichlet-perturbed weights (concentration = 20, 1000 simulations)
- Output: `outputs/mytourismsci_scores.parquet` — schema: state_code, year, economic_score, environmental_score, social_score, mytourismsci_score, rank, median_rank, rank_5th, rank_95th, rank_stability
- PCA within-pillar validation: `outputs/pillar_pca_validation.md` — only one flag (Economic 2025 at 37% PC1 variance, marginal)
- Figures: `outputs/figures/composite_heatmap_2025.png`, `outputs/figures/rank_trajectory_2020_2025.png`

**Known limitations already documented:**
1. Sarawak Environmental score (0.04) underestimates natural capital because buffer-fraction indicators normalize by state area (Sarawak is Malaysia's largest state, so absolute assets divided by huge area produces low fraction). This is a bias against geographically large states.
2. Forestry state-level data not integrated (source PDFs for 2022 + 2024 were scanned image-based, unrecoverable within timeline)
3. Waste per capita (SWCorp) only covers 7 federalized states — 9 states have NaN
4. Salaries & Wages Survey deferred (Social Pillar median wage indicator not populated)
5. Homestay data deferred (was PDF-only, not extracted; Social Pillar community tourism indicator missing)
6. Individual hotel geocoding failed due to Nominatim rate limits → pivoted to state-level buffer aggregation (loses granularity but state indicators are computable)
7. Some state master plans yielded 0 substantive commitments (Sabah, Kedah, Perak) due to graphic-heavy PDFs

---

## 2. What YOU are executing (AO2)

**Objective:** For each of the 16 Malaysian states, produce a 3-year forecast (2026, 2027, 2028) of the MyTourismSCI composite score AND diagnose the top-3 drivers of each state's current position using SHAP or a comparable feature-importance method.

**Deliverable list:**
1. `outputs/mytourismsci_forecast.parquet` — one row per (state_code, year in 2026–2028), columns: state_code, year, forecasted_score, forecast_ci_low, forecast_ci_high, model_used
2. `outputs/shap_drivers.parquet` — one row per (state_code, feature), columns: state_code, feature, shap_value, shap_rank (1 = most influential driver)
3. `outputs/model_comparison.md` — comparison of baseline vs ARIMA vs XGBoost with MAE on 2025 hold-out, justification for shipped model
4. `outputs/figures/forecast_trajectory.png` — line chart per state showing 2020–2025 actual + 2026–2028 forecast with CI ribbon
5. `outputs/wef_ttdi_validation.md` — comparison of national MyTourismSCI aggregate against Malaysia's WEF Travel & Tourism Development Index 2020–2025

**Time budget:** 4–6 hours total. Fits comfortably in a Saturday or split across Saturday morning + afternoon.

---

## 3. Step-by-step execution instructions

### Step 3.1 — Environment setup (10 min)

```powershell
cd D:\Downloads\DOSM_Datathon_StatsPower\mytourismsci
git pull origin main
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest  # confirm all tests pass — should see 60+ passing tests
```

If pytest fails, stop and debug before proceeding. If it passes, environment is good.

### Step 3.2 — Familiarize with the data (15 min)

Run this in a fresh Python session or notebook to understand what you're forecasting:

```python
import pandas as pd
scores = pd.read_parquet('outputs/mytourismsci_scores.parquet')
indicators = pd.read_parquet('data/final/state_year_indicators.parquet')
print(scores.head(20))
print(scores.groupby('state_code')['mytourismsci_score'].describe())
print(indicators.columns.tolist())
```

Read `docs/harmonization_methodology.md` and `outputs/pillar_pca_validation.md` while the code runs. Total time: 15 minutes for familiarity.

### Step 3.3 — Prepare features (30 min)

The AO2 task is: predict `mytourismsci_score` given (a) lagged own score, (b) lagged pillar sub-scores, and (c) raw indicators from `state_year_indicators.parquet`.

Create feature engineering script `src/analysis/ao2_features.py`:

```python
def build_features(scores_df, indicators_df):
    """
    Build feature matrix for AO2 forecasting.
    Returns DataFrame with columns:
        state_code, year, target_score (t), 
        score_t_minus_1, econ_t_minus_1, env_t_minus_1, social_t_minus_1,
        [all indicators from indicators_df],
        state_code_encoded (categorical)
    """
    # Merge on (state_code, year)
    df = scores_df.merge(indicators_df, on=['state_code', 'year'], how='left')
    
    # Lag features
    df = df.sort_values(['state_code', 'year'])
    for col in ['mytourismsci_score', 'economic_score', 'environmental_score', 'social_score']:
        df[f'{col}_lag1'] = df.groupby('state_code')[col].shift(1)
    
    # Drop first year per state (no lag available)
    df = df.dropna(subset=['mytourismsci_score_lag1'])
    
    return df
```

### Step 3.4 — Model comparison (2 hours)

**Baseline (naive):** predict year t = value at year t-1. This is your floor.

**Model 1 (ARIMA per-state):** Given only 6 years per state, ARIMA(1,0,0) or ARIMA(1,1,0) at most. Expect noisy forecasts. Report MAE on 2025 hold-out (train on 2020–2024, predict 2025) but DO NOT ship as primary — 6-year training is too thin for stable ARIMA.

**Model 2 (XGBoost pooled cross-state):** THIS IS YOUR RECOMMENDED PRIMARY MODEL.
- Pool all 96 observations
- Features: `mytourismsci_score_lag1`, pillar sub-score lags, all indicators, state_code as categorical
- Train/test split: train on 2020–2024, test on 2025
- Use `xgboost.XGBRegressor` with default hyperparameters first, then tune if MAE > 0.10

**Fallback if XGBoost unfamiliar:** use `sklearn.ensemble.RandomForestRegressor` with `permutation_importance` from `sklearn.inspection`. Same 96-observation setup. Simpler, still defensible.

Write `src/analysis/ao2_forecast.py`:

```python
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error

def train_xgboost(train_df, target_col='mytourismsci_score', drop_cols=['state_code', 'year']):
    X_train = train_df.drop(columns=[target_col] + drop_cols)
    y_train = train_df[target_col]
    # One-hot encode state_code separately if not already
    # X_train = pd.get_dummies(X_train, columns=['state_code'])
    model = XGBRegressor(n_estimators=200, max_depth=4, learning_rate=0.05, random_state=42)
    model.fit(X_train, y_train)
    return model
```

Evaluate all 3 models on the 2025 hold-out. Ship the one with lowest MAE. Document in `outputs/model_comparison.md`.

### Step 3.5 — Forecast 2026–2028 (30 min)

For the shipped model, produce recursive forecasts:
- Predict 2026 using 2025 as lag → save
- Predict 2027 using 2026 forecast as lag → save
- Predict 2028 using 2027 forecast as lag → save

Confidence intervals: use quantile regression forests OR bootstrap the residuals from the 2025 hold-out (`residuals = y_test - y_pred`), then add ± 1.96 × residual_std to point forecasts.

### Step 3.6 — SHAP driver diagnosis (45 min)

Only for the shipped model. Install if needed: `pip install shap`.

```python
import shap
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_train)
# shap_values shape: (n_observations, n_features)
```

For each state, get the SHAP values for the state's 2025 observation, sort by absolute value, take top-3 features. Save to `outputs/shap_drivers.parquet`.

**Interpretation for report:** for Sabah (rank #1), which features contribute most to its high score? Likely `environmental_pillar` and `economic_pillar` in balance. For Selangor (rank #2), likely `social_pillar` dominance. This is what the Research Lead uses in report Section 4 (Findings).

### Step 3.7 — WEF T&TDI national validation (30 min)

- WEF T&TDI 2024 edition has Malaysia scores. Find it via `https://www.weforum.org/reports/` search "Travel Tourism Development Index"
- Extract Malaysia's overall score for years 2020–2024 (biennial publication — interpolate missing years if needed, OR just use available years)
- Aggregate MyTourismSCI to national score per year: weighted average of state scores, weighted by state tourism receipts share (get receipts from `data/processed/dts/dts_jadual1.parquet`)
- Plot both trajectories 2020–2025 on same figure
- Write `outputs/wef_ttdi_validation.md`: describe direction of correspondence, note that WEF is competitiveness-focused vs MyTourismSCI sustainability-focused so partial divergence expected, cite this as external construct validity check

### Step 3.8 — Commit and push (10 min)

```powershell
git add outputs/mytourismsci_forecast.parquet outputs/shap_drivers.parquet outputs/model_comparison.md outputs/figures/forecast_trajectory.png outputs/wef_ttdi_validation.md src/analysis/ao2_*.py
git commit -m "AO2: XGBoost pooled forecast + SHAP driver diagnosis + WEF T&TDI validation"
git push origin main
```

Send a message to the team chat: "AO2 done. Forecast + drivers + WEF validation on main. Dashboard lead and Research lead unblocked."

---

## 4. If things go wrong

**XGBoost hyperparameters produce garbage forecasts:** try `n_estimators=500`, `max_depth=3`, `learning_rate=0.01`, `min_child_weight=2`. Grid-search over 3–4 values each if MAE still > 0.15.

**SHAP throws memory errors:** use `shap.KernelExplainer` with a small background dataset instead of `TreeExplainer` (slower but no memory blow-up).

**WEF T&TDI data hard to find:** substitute with Malaysia's UNWTO tourism arrivals ranking (public, easier to grab). Note the substitution in `wef_ttdi_validation.md`.

**Forecasts show unrealistic jumps (e.g., 2026 score < 0 or > 1):** clip to [0, 1] since the composite index is bounded. Report the clipping in `model_comparison.md`.

**You run out of time before finishing SHAP:** ship the forecast without SHAP as v1. Add a note that driver diagnosis is deferred to v2. Report Lead can still write Section 4 based on 2020–2025 trajectory analysis alone.

---

## 5. What NOT to do

- **Do not rebuild the composite index** or change weights. AO2 takes `mytourismsci_score` as fixed input from AO1.
- **Do not retrain AO1** or modify `outputs/mytourismsci_scores.parquet`.
- **Do not modify** any file under `data/processed/` or `data/final/` — those are consumed by dashboard and report too.
- **Do not add new indicators** — feature set is fixed by what's in `state_year_indicators.parquet`.
- **Do not attempt to forecast beyond 2028** — 3-year horizon is the AO2 scope, longer horizons compound forecast error.

---

## 6. Escalation

If blocked > 1 hour on any single issue:
1. Post specific error message + what you tried to team chat
2. Continue with fallback if listed above
3. If no fallback works, ship what you have + document the gap in `outputs/model_comparison.md`

**Primary developer will NOT be reachable Saturday–Monday.** Ship a working v1 rather than block on perfection.

---

## 7. Definition of done

- [ ] `outputs/mytourismsci_forecast.parquet` exists with 48 rows (16 states × 3 years)
- [ ] `outputs/shap_drivers.parquet` exists with ≥ 48 rows (16 states × top-3 features)
- [ ] `outputs/model_comparison.md` exists with MAE numbers for all 3 models
- [ ] `outputs/figures/forecast_trajectory.png` shows all 16 states with CI ribbons
- [ ] `outputs/wef_ttdi_validation.md` exists with trajectory comparison
- [ ] All AO2 code in `src/analysis/ao2_*.py`
- [ ] At least 3 tests in `tests/test_ao2.py`
- [ ] Everything committed to `main` with clear commit messages
- [ ] Team notified via chat

**Time to complete: 4–6 hours. Deadline: Monday 22 Sep 6:00 PM MYT.**