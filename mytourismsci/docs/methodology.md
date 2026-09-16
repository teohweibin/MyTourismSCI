# Methodology

## Composite Index Construction

Methodological framework follows OECD/JRC (2008) Handbook on Constructing
Composite Indicators, with pillar structure aligned to UN Tourism MST
framework as scoped for Malaysia in the UNESCAP 2020 study.

### Normalisation

Min-max normalisation to [0, 1] range per indicator.

### Weighting

Equal weighting within pillars (default), with PCA-derived weights as
robustness check.

### Aggregation

Geometric mean across pillars, following UNDP HDI methodology.

### Robustness

Monte Carlo simulation over weighting schemes and normalisation variants,
following OECD/JRC (2008) Chapter 5 guidance.

## Forecasting (AO2)

Naive baseline, ARIMA, and XGBoost models in a horse-race comparison.
SHAP values provide state-specific pressure diagnostics.

## LLM-Assisted Policy Extraction (AO3)

Structured extraction using Claude Sonnet 4.5 with human validation.
Target precision >= 85% on stratified sample.
