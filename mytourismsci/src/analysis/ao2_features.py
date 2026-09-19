"""
AO2 — Feature engineering for MyTourismSCI forecasting.

Builds the feature matrix used by the model-comparison horse-race
(naive / ARIMA / XGBoost) and by the final shipped forecasting model.

Design notes
------------
- Target: mytourismsci_score at year t.
- Features: own-score and pillar-score lags (t-1), plus the full set of
  contemporaneous (year-t) raw indicators from state_year_indicators.parquet.
- The first observed year per state (2020) is dropped because it has no
  lag available -> 16 states x 5 remaining years (2021-2025) = 80 rows.
- Missing indicator values are left as explicit NaN. XGBoost's default
  tree-splitting handles NaN natively (it learns a default split
  direction for missing values), so no imputation is performed here,
  consistent with the harmonization methodology's explicit-NaN policy.
"""
import pandas as pd

LAG_SOURCE_COLS = [
    "mytourismsci_score",
    "economic_score",
    "environmental_score",
    "social_score",
]

ID_COLS = ["state_code", "year"]
TARGET_COL = "mytourismsci_score"


def build_features(scores_df: pd.DataFrame, indicators_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build feature matrix for AO2 forecasting.

    Parameters
    ----------
    scores_df : DataFrame from outputs/mytourismsci_scores.parquet
    indicators_df : DataFrame from data/final/state_year_indicators.parquet

    Returns
    -------
    DataFrame, one row per (state_code, year), year in 2021-2025, with:
        state_code, year, mytourismsci_score (target),
        mytourismsci_score_lag1, economic_score_lag1,
        environmental_score_lag1, social_score_lag1,
        <all indicator columns from indicators_df, contemporaneous (year t)>
    """
    df = scores_df.merge(indicators_df, on=ID_COLS, how="left")
    df = df.sort_values(ID_COLS).reset_index(drop=True)

    for col in LAG_SOURCE_COLS:
        df[f"{col}_lag1"] = df.groupby("state_code")[col].shift(1)

    df = df.dropna(subset=["mytourismsci_score_lag1"]).reset_index(drop=True)

    return df


def get_feature_columns(df: pd.DataFrame) -> list:
    """
    Return the list of model input feature columns (excludes identifiers,
    the target, and AO1's own rank/CI bookkeeping columns which are not
    legitimate predictive features — they are *derived from* the target).
    """
    exclude = {
        "year",  # state_code IS kept as a categorical feature; year is dropped
        TARGET_COL,
        "rank", "median_rank", "rank_5th", "rank_95th", "rank_stability",
        "economic_score", "environmental_score", "social_score",  # contemporaneous pillar scores
        # ^ excluded because they are components that mechanically sum into
        # the target via the AO1 geometric-mean aggregation; including them
        # would leak the target. Only their LAGGED versions are used.
    }
    return [c for c in df.columns if c not in exclude]


if __name__ == "__main__":
    scores = pd.read_parquet("outputs/mytourismsci_scores.parquet")
    indicators = pd.read_parquet("data/final/state_year_indicators.parquet")
    feat = build_features(scores, indicators)
    print(f"Feature matrix: {feat.shape[0]} rows x {feat.shape[1]} cols")
    print(f"Years present: {sorted(feat['year'].unique())}")
    print(f"Feature columns ({len(get_feature_columns(feat))}):")
    print(get_feature_columns(feat))
