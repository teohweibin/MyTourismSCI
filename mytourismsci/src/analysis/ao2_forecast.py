"""AO2: Forecast MyTourismSCI three years forward per state.

Approach: Naive baseline vs ARIMA vs XGBoost horse-race.
SHAP values for interpretable state-specific pressure diagnostics.

Inputs: data/final/state_year_indicators.parquet
Outputs: outputs/ (forecasts, SHAP plots, model comparison)
Dependencies: pandas, statsmodels, xgboost, shap
"""
