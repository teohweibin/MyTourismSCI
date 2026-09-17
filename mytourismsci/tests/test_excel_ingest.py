"""Tests for DTS and TSA Excel ingestion module.

Tests that require actual Excel files are skipped if files are not present
(they are gitignored in data/raw/).
"""

from pathlib import Path

import pandas as pd
import pytest

from src.harmonization.state_codes import VALID_CODES

DTS_ROOT = Path("data/raw/dts")
TSA_ROOT = Path("data/raw/tsa")

JOHOR_2025 = DTS_ROOT / "2025" / "Johor_dts_2025.xlsx"
JOHOR_2020 = DTS_ROOT / "2020" / "Table of Publication_Johor.xlsx"
TSA_2025 = TSA_ROOT / "tourism_2025.xlsx"

skip_no_dts = pytest.mark.skipif(
    not JOHOR_2025.exists(), reason="DTS test file not present"
)
skip_no_tsa = pytest.mark.skipif(
    not TSA_2025.exists(), reason="TSA test file not present"
)


@pytest.fixture
def johor_2025_path():
    return JOHOR_2025


@pytest.fixture
def tsa_2025_path():
    return TSA_2025


class TestModuleImports:
    def test_module_imports_cleanly(self):
        import src.ingestion.excel_ingest  # noqa: F401

    def test_entry_points_exist(self):
        from src.ingestion.excel_ingest import (
            ingest_dts_state_files,
            ingest_tsa_national,
        )
        assert callable(ingest_dts_state_files)
        assert callable(ingest_tsa_national)

    def test_parsers_exist(self):
        from src.ingestion.excel_ingest import (
            parse_dts_jadual1,
            parse_dts_jadual10,
            parse_dts_jadual14_15,
        )
        assert callable(parse_dts_jadual1)
        assert callable(parse_dts_jadual10)
        assert callable(parse_dts_jadual14_15)


class TestFileDiscovery:
    def test_discover_dts_files_returns_list(self):
        from src.ingestion.excel_ingest import discover_dts_files
        result = discover_dts_files()
        assert isinstance(result, list)

    @skip_no_dts
    def test_discover_dts_finds_files(self):
        from src.ingestion.excel_ingest import discover_dts_files
        result = discover_dts_files()
        assert len(result) > 0
        entry = result[0]
        assert "path" in entry
        assert "year" in entry
        assert "state_code" in entry
        assert entry["state_code"] in VALID_CODES

    def test_discover_tsa_files_returns_list(self):
        from src.ingestion.excel_ingest import discover_tsa_files
        result = discover_tsa_files()
        assert isinstance(result, list)

    @skip_no_tsa
    def test_discover_tsa_finds_files(self):
        from src.ingestion.excel_ingest import discover_tsa_files
        result = discover_tsa_files()
        assert len(result) > 0
        assert "year" in result[0]

    def test_discover_dts_empty_dir(self, tmp_path):
        from src.ingestion.excel_ingest import discover_dts_files
        result = discover_dts_files(tmp_path)
        assert result == []


class TestFilenameExtraction:
    def test_table_of_publication_format(self):
        from src.ingestion.excel_ingest import _extract_state_from_filename
        assert _extract_state_from_filename("Table of Publication_Johor.xlsx") == "Johor"
        assert _extract_state_from_filename("Table of Publication_WP Kuala Lumpur.xlsx") == "WP Kuala Lumpur"

    def test_state_dts_year_format(self):
        from src.ingestion.excel_ingest import _extract_state_from_filename
        assert _extract_state_from_filename("Johor_dts_2025.xlsx") == "Johor"
        assert _extract_state_from_filename("Negeri_Sembilan_dts_2024.xlsx") == "Negeri Sembilan"

    def test_lowercase_no_separator_format(self):
        from src.ingestion.excel_ingest import _extract_state_from_filename
        raw = _extract_state_from_filename("negerisembilan_dts_2022.xlsx")
        assert raw == "Negeri Sembilan"

    def test_kl_alias(self):
        from src.ingestion.excel_ingest import _extract_state_from_filename
        raw = _extract_state_from_filename("KL_dts_2025")
        assert raw == "W.P. Kuala Lumpur"

    def test_unrecognised_returns_none(self):
        from src.ingestion.excel_ingest import _extract_state_from_filename
        assert _extract_state_from_filename("random_file.xlsx") is None


@skip_no_dts
class TestJadual1Parser:
    def test_johor_2025_shape(self):
        from src.ingestion.excel_ingest import parse_dts_jadual1
        df = parse_dts_jadual1(JOHOR_2025, "JOH", 2025)
        assert isinstance(df, pd.DataFrame)
        assert set(df.columns) == {"state_code", "year", "indicator", "value"}
        assert (df["state_code"] == "JOH").all()

    def test_johor_2025_indicators(self):
        from src.ingestion.excel_ingest import parse_dts_jadual1
        df = parse_dts_jadual1(JOHOR_2025, "JOH", 2025)
        expected = {
            "tourism_receipts_rm_mil",
            "domestic_visitors_000",
            "tourism_trips_000",
            "avg_receipts_per_capita_rm",
            "avg_receipts_per_trip_rm",
            "avg_length_of_stay",
        }
        assert set(df["indicator"].unique()) == expected

    def test_johor_2025_years_in_range(self):
        from src.ingestion.excel_ingest import parse_dts_jadual1
        df = parse_dts_jadual1(JOHOR_2025, "JOH", 2025)
        assert df["year"].min() >= 2020
        assert df["year"].max() <= 2025

    def test_johor_2025_no_growth_rates(self):
        from src.ingestion.excel_ingest import parse_dts_jadual1
        df = parse_dts_jadual1(JOHOR_2025, "JOH", 2025)
        for ind in df["indicator"].unique():
            sub = df[df["indicator"] == ind]
            assert len(sub) == sub["year"].nunique()

    def test_2020_format_works(self):
        from src.ingestion.excel_ingest import parse_dts_jadual1
        if not JOHOR_2020.exists():
            pytest.skip("2020 file not available")
        df = parse_dts_jadual1(JOHOR_2020, "JOH", 2020)
        assert len(df) > 0
        assert 2020 in df["year"].values


@skip_no_dts
class TestJadual10Parser:
    def test_johor_2025_od_matrix(self):
        from src.ingestion.excel_ingest import parse_dts_jadual10
        df = parse_dts_jadual10(JOHOR_2025, "JOH", 2025)
        assert set(df.columns) == {"file_year", "origin_code", "dest_code", "visitors_000"}
        assert len(df["origin_code"].unique()) == 16
        assert len(df["dest_code"].unique()) == 16

    def test_all_state_codes_valid(self):
        from src.ingestion.excel_ingest import parse_dts_jadual10
        df = parse_dts_jadual10(JOHOR_2025, "JOH", 2025)
        assert set(df["origin_code"].unique()).issubset(VALID_CODES)
        assert set(df["dest_code"].unique()).issubset(VALID_CODES)


@skip_no_dts
class TestJadual14_15Parser:
    def test_johor_2025_hotels(self):
        from src.ingestion.excel_ingest import parse_dts_jadual14_15
        df = parse_dts_jadual14_15(JOHOR_2025, "JOH", 2025)
        assert "star_rating" in df["table"].values
        assert "location" in df["table"].values

    def test_star_rating_categories(self):
        from src.ingestion.excel_ingest import parse_dts_jadual14_15
        df = parse_dts_jadual14_15(JOHOR_2025, "JOH", 2025)
        star = df[df["table"] == "star_rating"]
        assert len(star) >= 8  # 5 stars + 3 orchids + unrated

    def test_hotel_room_positive(self):
        from src.ingestion.excel_ingest import parse_dts_jadual14_15
        df = parse_dts_jadual14_15(JOHOR_2025, "JOH", 2025)
        assert (df["hotels"].dropna() > 0).all()
        assert (df["rooms"].dropna() > 0).all()


@skip_no_tsa
class TestTSAParser:
    def test_indicator_inbound(self):
        from src.ingestion.excel_ingest import _parse_tsa_indicator_inbound
        df = _parse_tsa_indicator_inbound(TSA_2025)
        assert "visitor_arrivals_total" in df["indicator"].values
        assert "avg_occupancy_rate_pct" in df["indicator"].values

    def test_indicator_domestik_states(self):
        from src.ingestion.excel_ingest import _parse_tsa_indicator_domestik
        df = _parse_tsa_indicator_domestik(TSA_2025)
        state_rows = df[df["state_code"] != "NATIONAL"]
        state_codes = set(state_rows["state_code"].unique())
        assert state_codes == VALID_CODES

    def test_economic_no_growth_rates(self):
        from src.ingestion.excel_ingest import _parse_tsa_economic_tables
        df = _parse_tsa_economic_tables(TSA_2025)
        for ind in df["indicator"].unique():
            sub = df[df["indicator"] == ind]
            assert len(sub) == sub["year"].nunique()

    def test_tourism_gva_present(self):
        from src.ingestion.excel_ingest import _parse_tsa_economic_tables
        df = _parse_tsa_economic_tables(TSA_2025)
        assert "tourism_gva_rm_mil" in df["indicator"].values
        assert "gdp_rm_mil" in df["indicator"].values
        assert "tourism_employment_000" in df["indicator"].values
