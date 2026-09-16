"""Tests for OpenDOSM API ingestion module.

Uses mocked API responses — does not hit the live API.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.ingestion.opendosm_api import (
    _extract_year,
    _normalize_states,
    fetch_opendosm,
)


MOCK_POPULATION_RESPONSE = [
    {"age": "overall_age", "sex": "overall_sex", "date": "2020-01-01",
     "state": "Johor", "ethnicity": "overall_ethnicity", "population": 4009.7},
    {"age": "overall_age", "sex": "overall_sex", "date": "2020-01-01",
     "state": "Kedah", "ethnicity": "overall_ethnicity", "population": 2131.4},
    {"age": "overall_age", "sex": "overall_sex", "date": "2021-01-01",
     "state": "Johor", "ethnicity": "overall_ethnicity", "population": 4050.1},
]

MOCK_ARRIVALS_RESPONSE = [
    {"date": "2020-01-01", "country": "ALL", "arrivals": 2923053,
     "arrivals_male": 1598823, "arrivals_female": 1324230},
    {"date": "2020-02-01", "country": "ALL", "arrivals": 1997322,
     "arrivals_male": 1186644, "arrivals_female": 810678},
]


class TestFetchOpendosm:
    @patch("src.ingestion.opendosm_api.requests.get")
    def test_returns_dataframe_on_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_POPULATION_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        df = fetch_opendosm("population_state")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert "state" in df.columns
        assert "population" in df.columns

    @patch("src.ingestion.opendosm_api.requests.get")
    def test_raises_on_non_list_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"error": "something"}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with pytest.raises(ValueError, match="Expected list"):
            fetch_opendosm("bad_slug")

    @patch("src.ingestion.opendosm_api.requests.get")
    @patch("src.ingestion.opendosm_api.sleep")
    def test_retries_on_connection_error(self, mock_sleep, mock_get):
        import requests as req

        mock_get.side_effect = [
            req.ConnectionError("network down"),
            MagicMock(
                status_code=200,
                json=MagicMock(return_value=MOCK_POPULATION_RESPONSE),
                raise_for_status=MagicMock(),
            ),
        ]

        df = fetch_opendosm("population_state", max_retries=2)
        assert len(df) == 3
        assert mock_get.call_count == 2


class TestNormalizeStates:
    def test_valid_states_normalised(self):
        df = pd.DataFrame({"state": ["Johor", "Penang", "W.P. Kuala Lumpur"]})
        result = _normalize_states(df)
        assert list(result["state_code"]) == ["JOH", "PNG", "KUL"]

    def test_national_rows_dropped(self):
        df = pd.DataFrame({"state": ["Johor", "Malaysia", "Kedah"]})
        result = _normalize_states(df)
        assert len(result) == 2
        assert "Malaysia" not in result["state_code"].values

    def test_all_16_states_handled(self):
        from src.harmonization.state_codes import CANONICAL_STATE_CODES
        df = pd.DataFrame({"state": list(CANONICAL_STATE_CODES.keys())})
        result = _normalize_states(df)
        assert len(result) == 16


class TestExtractYear:
    def test_extracts_year_from_date_string(self):
        df = pd.DataFrame({"date": ["2020-01-01", "2021-06-15", "2022-12-31"]})
        result = _extract_year(df)
        assert list(result["year"]) == [2020, 2021, 2022]

    def test_does_not_modify_original(self):
        df = pd.DataFrame({"date": ["2020-01-01"]})
        _extract_year(df)
        assert "year" not in df.columns


class TestPaginationLogic:
    @patch("src.ingestion.opendosm_api.requests.get")
    def test_single_request_for_small_dataset(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_ARRIVALS_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        df = fetch_opendosm("arrivals")
        assert mock_get.call_count == 1
        call_params = mock_get.call_args[1].get("params") or mock_get.call_args[0][1] if len(mock_get.call_args[0]) > 1 else mock_get.call_args[1]["params"]
        assert call_params["limit"] == 100_000
