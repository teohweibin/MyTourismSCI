"""Tests for AO3 gap analysis.

Inputs:  src/analysis/ao3_gap_analysis.py
Outputs: Assertions on gap classification, commitment mapping, brief generation
Dependencies: pytest, pandas, numpy
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from analysis.ao3_gap_analysis import (
    COMMITMENT_MAP,
    UNMAPPABLE_TYPES,
    classify_gap,
    generate_state_brief,
)


class TestClassifyGap:
    def test_already_met(self):
        status, req, obs = classify_gap(
            current=100.0, target=80.0, target_year=2030,
            observed_cagr=0.05,
        )
        assert status == "already_met"
        assert req == 0.0

    def test_on_track(self):
        # current=50, target=100, target_year=2030, 5 years remaining
        # required_annual = (100-50)/5 = 10
        # observed_annual = 50 * 0.25 = 12.5 >= 0.9 * 10 = 9
        status, req, obs = classify_gap(
            current=50.0, target=100.0, target_year=2030,
            observed_cagr=0.25, reference_year=2025,
        )
        assert status == "on_track"
        assert req == pytest.approx(10.0)
        assert obs == pytest.approx(12.5)

    def test_at_risk(self):
        # current=50, target=100, 5 years → required=10
        # observed = 50 * 0.12 = 6.0; 0.5*10=5 <= 6 < 0.9*10=9
        status, req, obs = classify_gap(
            current=50.0, target=100.0, target_year=2030,
            observed_cagr=0.12, reference_year=2025,
        )
        assert status == "at_risk"

    def test_off_track(self):
        # current=50, target=100, 5 years → required=10
        # observed = 50 * 0.05 = 2.5 < 0.5*10=5
        status, req, obs = classify_gap(
            current=50.0, target=100.0, target_year=2030,
            observed_cagr=0.05, reference_year=2025,
        )
        assert status == "off_track"

    def test_zero_cagr(self):
        status, req, obs = classify_gap(
            current=50.0, target=100.0, target_year=2030,
            observed_cagr=None, reference_year=2025,
        )
        assert status == "off_track"
        assert obs == 0.0


class TestCommitmentMapping:
    def test_mappable_types_have_indicators(self):
        for ctype, config in COMMITMENT_MAP.items():
            assert "indicator" in config
            assert isinstance(config["indicator"], str)

    def test_unmappable_types_disjoint(self):
        assert UNMAPPABLE_TYPES.isdisjoint(set(COMMITMENT_MAP.keys()))

    def test_visitor_arrivals_mapped(self):
        assert "visitor_arrivals" in COMMITMENT_MAP
        assert COMMITMENT_MAP["visitor_arrivals"]["indicator"] == "domestic_visitors_000"

    def test_employment_unmappable(self):
        assert "employment" in UNMAPPABLE_TYPES


class TestBriefGeneration:
    def test_brief_smoke(self):
        gap_df = pd.DataFrame({
            "state": ["KUL"],
            "commitment_type": ["visitor_arrivals"],
            "indicator": ["domestic_visitors_000"],
            "target_value": [22.5],
            "target_unit": ["million domestic tourists"],
            "target_converted": [22500.0],
            "target_year": [2040],
            "current_value": [35000.0],
            "observed_cagr": [0.23],
            "observed_annual_change": [0.0],
            "required_annual_change": [0.0],
            "status": ["already_met"],
            "verbatim_quote": ["Tourist arrival (million people) Domestic 22.5"],
            "source_doc": ["test.pdf"],
            "source_page": [1],
            "sustainability_dimension": ["economic"],
        })
        scores = pd.DataFrame({
            "state_code": ["KUL", "KUL"],
            "year": [2020, 2025],
            "mytourismsci_score": [0.30, 0.36],
            "rank": [6, 6],
            "economic_score": [0.51, 0.48],
            "environmental_score": [0.11, 0.12],
            "social_score": [0.87, 0.99],
        })
        indicators = pd.DataFrame()

        brief = generate_state_brief("KUL", gap_df, scores, indicators)
        assert "Kuala Lumpur" in brief
        assert "already_met" in brief
        assert "0.360" in brief
        assert "Pillar Trajectory" in brief
