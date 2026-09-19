"""Tests for AO2 forecasting + driver diagnosis pipeline."""
import numpy as np
import pandas as pd
import pytest

from src.analysis.ao2_features import build_features, get_feature_columns, TARGET_COL


@pytest.fixture
def scores_df():
    return pd.read_parquet("outputs/mytourismsci_scores.parquet")


@pytest.fixture
def indicators_df():
    return pd.read_parquet("data/final/state_year_indicators.parquet")


def test_build_features_shape(scores_df, indicators_df):
    feat = build_features(scores_df, indicators_df)
    # 16 states x 5 years (2021-2025) after dropping the no-lag first year
    assert feat.shape[0] == 16 * 5
    assert set(feat["year"].unique()) == {2021, 2022, 2023, 2024, 2025}


def test_no_leakage_columns_in_features(scores_df, indicators_df):
    feat = build_features(scores_df, indicators_df)
    cols = get_feature_columns(feat)
    leaky = {"economic_score", "environmental_score", "social_score",
             "rank", "median_rank", "rank_5th", "rank_95th", "rank_stability",
             TARGET_COL}
    assert leaky.isdisjoint(set(cols)), (
        "Contemporaneous pillar scores / AO1 rank columns must not be "
        "used as predictive features (target leakage)."
    )


def test_lag_features_present(scores_df, indicators_df):
    feat = build_features(scores_df, indicators_df)
    for col in ["mytourismsci_score_lag1", "economic_score_lag1",
                "environmental_score_lag1", "social_score_lag1"]:
        assert col in feat.columns
        assert feat[col].notna().all()


def test_forecast_output_shape():
    forecast = pd.read_parquet("outputs/mytourismsci_forecast.parquet")
    assert forecast.shape[0] == 16 * 3  # 16 states x 3 years
    assert set(forecast["year"].unique()) == {2026, 2027, 2028}
    required_cols = {"state_code", "year", "forecasted_score",
                      "forecast_ci_low", "forecast_ci_high", "model_used"}
    assert required_cols.issubset(forecast.columns)


def test_forecast_bounded_and_ci_ordered():
    forecast = pd.read_parquet("outputs/mytourismsci_forecast.parquet")
    assert (forecast["forecasted_score"].between(0, 1)).all()
    assert (forecast["forecast_ci_low"] <= forecast["forecasted_score"]).all()
    assert (forecast["forecasted_score"] <= forecast["forecast_ci_high"]).all()


def test_shap_drivers_output():
    shap_df = pd.read_parquet("outputs/shap_drivers.parquet")
    assert shap_df.shape[0] >= 16 * 3  # >= 16 states x top-3 features
    assert set(shap_df["state_code"].unique()).issubset(
        {"JOH", "KDH", "KTN", "KUL", "LBN", "MLK", "NSN", "PHG",
         "PJY", "PLS", "PNG", "PRK", "SBH", "SGR", "SWK", "TRG"}
    )
    # exactly top-3 ranked per state
    ranks_per_state = shap_df.groupby("state_code")["shap_rank"].apply(set)
    assert all(r == {1, 2, 3} for r in ranks_per_state)
