"""AO1: Construct and validate MyTourismSCI composite index.

Methodology: OECD/JRC 2008 Handbook, UNDP HDI geometric mean aggregation,
OPHI MPI sub-national composite methodology (as adopted by DOSM).
Pillar structure aligned to UN Tourism MST framework.

Inputs: data/final/state_year_indicators.parquet
Outputs: outputs/ (index scores, PCA results, Monte Carlo robustness)
Dependencies: pandas, scikit-learn, numpy
"""
