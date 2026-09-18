"""Tests for the unified state-year indicator table.

Inputs:  src/harmonization/build_unified_table.py
Outputs: Assertions on merge correctness, derived formulas, pillar labeling,
         missingness handling, and output schema
Dependencies: pytest, pandas, numpy
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from harmonization.build_unified_table import (
    build_unified_table,
    compute_derived,
    to_long_format,
    PILLAR_MAP,
    TARGET_STATES,
    TARGET_YEARS,
)


@pytest.fixture(scope="module")
def wide_table() -> pd.DataFrame:
    return build_unified_table()


class TestMergeCorrectness:
    def test_shape(self, wide_table: pd.DataFrame) -> None:
        assert wide_table.shape[0] == len(TARGET_STATES) * len(TARGET_YEARS)
        assert "state_code" in wide_table.columns
        assert "year" in wide_table.columns

    def test_known_state_year(self, wide_table: pd.DataFrame) -> None:
        row = wide_table[
            (wide_table["state_code"] == "SGR") & (wide_table["year"] == 2022)
        ]
        assert len(row) == 1
        assert row["domestic_visitors_000"].notna().all()
        assert row["wqi_annual"].notna().all()


class TestDerivedIndicators:
    def test_tourism_concentration_ratio(self, wide_table: pd.DataFrame) -> None:
        row = wide_table[
            (wide_table["state_code"] == "JOH")
            & (wide_table["year"] == 2020)
            & wide_table["population"].notna()
        ]
        if len(row) == 1:
            expected = (
                row["domestic_visitors_000"].iloc[0] / row["population"].iloc[0]
            )
            assert np.isclose(
                row["tourism_concentration_ratio"].iloc[0], expected, rtol=1e-6
            )

    def test_expenditure_per_visitor(self, wide_table: pd.DataFrame) -> None:
        row = wide_table[
            (wide_table["state_code"] == "KUL") & (wide_table["year"] == 2022)
        ]
        if len(row) == 1 and row["domestic_visitors_000"].notna().all():
            expected = (
                row["tourism_receipts_rm_mil"].iloc[0]
                * 1000
                / row["domestic_visitors_000"].iloc[0]
            )
            assert np.isclose(
                row["expenditure_per_visitor"].iloc[0], expected, rtol=1e-6
            )

    def test_green_hotel_share_bounded(self, wide_table: pd.DataFrame) -> None:
        valid = wide_table["green_hotel_share"].dropna()
        assert (valid >= 0).all()
        assert (valid <= 1).all()


class TestPillarLabeling:
    def test_all_indicators_have_pillar(self, wide_table: pd.DataFrame) -> None:
        long = to_long_format(wide_table)
        unassigned = long[long["pillar"] == "Unassigned"]["indicator_name"].unique()
        allowed_unassigned = {"total_hotels"}
        actual_unassigned = set(unassigned) - allowed_unassigned
        assert len(actual_unassigned) == 0, f"Unassigned indicators: {actual_unassigned}"

    def test_pillar_values(self, wide_table: pd.DataFrame) -> None:
        long = to_long_format(wide_table)
        valid_pillars = {"Economic", "Environmental", "Social", "Unassigned"}
        assert set(long["pillar"].unique()).issubset(valid_pillars)


class TestMissingnessHandling:
    def test_no_zeros_for_missing(self, wide_table: pd.DataFrame) -> None:
        row = wide_table[
            (wide_table["state_code"] == "TRG") & (wide_table["year"] == 2024)
        ]
        assert row["population"].isna().all() or row["population"].iloc[0] > 0

    def test_international_arrivals_all_nan(self, wide_table: pd.DataFrame) -> None:
        assert wide_table["international_arrivals_share"].isna().all()
