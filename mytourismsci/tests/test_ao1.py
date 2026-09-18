"""Tests for AO1 composite index construction.

Inputs:  src/analysis/ao1_composite_index.py
Outputs: Assertions on normalization, geometric mean, weights, PCA, Monte Carlo
Dependencies: pytest, pandas, numpy
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from analysis.ao1_composite_index import (
    EPSILON,
    INDICATOR_CONFIG,
    MC_SEED,
    PILLAR_WEIGHTS,
    PILLARS,
    TARGET_YEARS,
    aggregate_pillars,
    compute_composite,
    monte_carlo_sensitivity,
    normalize_minmax,
    pca_validation,
    run_ao1,
)


@pytest.fixture(scope="module")
def ao1_result():
    df, kept = run_ao1()
    return df, kept


class TestNormalization:
    def test_minmax_bounds(self, ao1_result) -> None:
        df, kept = ao1_result
        for ind in kept:
            col = f"{ind}_norm"
            vals = df[col].dropna()
            assert vals.min() >= -1e-9, f"{col} has values below 0"
            assert vals.max() <= 1.0 + 1e-9, f"{col} has values above 1"

    def test_minmax_within_year(self, ao1_result) -> None:
        df, kept = ao1_result
        for year in TARGET_YEARS:
            ydf = df[df["year"] == year]
            for ind in kept:
                col = f"{ind}_norm"
                vals = ydf[col].dropna()
                if len(vals) > 1:
                    assert abs(vals.min()) < 1e-6 or abs(vals.max() - 1.0) < 1e-6


class TestGeometricMean:
    def test_pillar_scores_bounded(self, ao1_result) -> None:
        df, _ = ao1_result
        for pillar in PILLARS:
            col = f"{pillar.lower()}_score"
            vals = df[col].dropna()
            assert vals.min() >= 0, f"{col} below 0"
            assert vals.max() <= 1.0 + 1e-6, f"{col} above 1"

    def test_composite_bounded(self, ao1_result) -> None:
        df, _ = ao1_result
        vals = df["mytourismsci_score"].dropna()
        assert vals.min() >= 0
        assert vals.max() <= 1.0 + 1e-6


class TestWeightApplication:
    def test_weights_sum_to_one(self) -> None:
        assert abs(sum(PILLAR_WEIGHTS.values()) - 1.0) < 1e-9

    def test_composite_uses_weights(self, ao1_result) -> None:
        df, _ = ao1_result
        row = df.iloc[0]
        scores = [row[f"{p.lower()}_score"] for p in PILLARS]
        weights = [PILLAR_WEIGHTS[p] for p in PILLARS]
        log_comp = sum(w * np.log(max(s, EPSILON)) for s, w in zip(scores, weights))
        expected = np.exp(log_comp)
        assert np.isclose(row["mytourismsci_score"], np.clip(expected, 0, 1), rtol=1e-4)


class TestPCAShape:
    def test_pca_report_nonempty(self, ao1_result) -> None:
        df, kept = ao1_result
        report = pca_validation(df, kept)
        assert "Economic" in report
        assert "Environmental" in report
        assert "Social" in report
        assert "PC1 Loading" in report


class TestMonteCarloReproducibility:
    def test_fixed_seed_deterministic(self, ao1_result) -> None:
        df, _ = ao1_result
        _, summary1 = monte_carlo_sensitivity(df)
        _, summary2 = monte_carlo_sensitivity(df)
        pd.testing.assert_frame_equal(summary1, summary2)


class TestRankStability:
    def test_stability_bounded(self, ao1_result) -> None:
        df, _ = ao1_result
        _, summary = monte_carlo_sensitivity(df)
        assert (summary["rank_stability"] >= 0).all()
        assert (summary["rank_stability"] <= 1).all()

    def test_rank_count(self, ao1_result) -> None:
        df, _ = ao1_result
        for year in TARGET_YEARS:
            ydf = df[df["year"] == year]
            assert ydf["rank"].min() == 1
            assert ydf["rank"].max() == 16
