"""Tests for state code normalisation module."""

import pytest

from src.harmonization.state_codes import (
    CANONICAL_STATE_CODES,
    VALID_CODES,
    normalize_state_name,
)


class TestCanonicalCodes:
    def test_16_states_exist(self):
        assert len(CANONICAL_STATE_CODES) == 16

    def test_16_unique_codes(self):
        assert len(VALID_CODES) == 16

    def test_all_codes_three_letters(self):
        for code in VALID_CODES:
            assert len(code) == 3
            assert code.isupper()


class TestNormalizeStateName:
    @pytest.mark.parametrize("name,expected", [
        ("Johor", "JOH"),
        ("Kedah", "KDH"),
        ("Kelantan", "KTN"),
        ("Melaka", "MLK"),
        ("Negeri Sembilan", "NSN"),
        ("Pahang", "PHG"),
        ("Pulau Pinang", "PNG"),
        ("Perak", "PRK"),
        ("Perlis", "PLS"),
        ("Selangor", "SGR"),
        ("Terengganu", "TRG"),
        ("Sabah", "SBH"),
        ("Sarawak", "SWK"),
        ("W.P. Kuala Lumpur", "KUL"),
        ("W.P. Labuan", "LBN"),
        ("W.P. Putrajaya", "PJY"),
    ])
    def test_canonical_names(self, name, expected):
        assert normalize_state_name(name) == expected

    def test_code_passthrough(self):
        assert normalize_state_name("JOH") == "JOH"
        assert normalize_state_name("KUL") == "KUL"
        assert normalize_state_name("SBH") == "SBH"

    def test_case_insensitive(self):
        assert normalize_state_name("johor") == "JOH"
        assert normalize_state_name("JOHOR") == "JOH"
        assert normalize_state_name("joh") == "JOH"
        assert normalize_state_name("selangor") == "SGR"

    def test_whitespace_stripped(self):
        assert normalize_state_name("  Johor  ") == "JOH"
        assert normalize_state_name("\tSelangor\n") == "SGR"

    @pytest.mark.parametrize("alias,expected", [
        ("Penang", "PNG"),
        ("P. Pinang", "PNG"),
        ("Malacca", "MLK"),
        ("N. Sembilan", "NSN"),
        ("N.Sembilan", "NSN"),
        ("KL", "KUL"),
        ("Kuala Lumpur", "KUL"),
        ("Labuan", "LBN"),
        ("Putrajaya", "PJY"),
    ])
    def test_english_aliases(self, alias, expected):
        assert normalize_state_name(alias) == expected

    @pytest.mark.parametrize("alias,expected", [
        ("Wilayah Persekutuan Kuala Lumpur", "KUL"),
        ("Wilayah Persekutuan Labuan", "LBN"),
        ("Wilayah Persekutuan Putrajaya", "PJY"),
        ("Kedah Darul Aman", "KDH"),
        ("Selangor Darul Ehsan", "SGR"),
    ])
    def test_malay_full_forms(self, alias, expected):
        assert normalize_state_name(alias) == expected

    def test_malay_and_english_resolve_same(self):
        assert normalize_state_name("Penang") == normalize_state_name("Pulau Pinang")
        assert normalize_state_name("Malacca") == normalize_state_name("Melaka")
        assert normalize_state_name("KL") == normalize_state_name("Wilayah Persekutuan Kuala Lumpur")

    def test_unknown_raises_valueerror(self):
        with pytest.raises(ValueError, match="Unknown state name"):
            normalize_state_name("Not A State")

    def test_empty_string_raises_valueerror(self):
        with pytest.raises(ValueError, match="empty"):
            normalize_state_name("")

    def test_whitespace_only_raises_valueerror(self):
        with pytest.raises(ValueError, match="empty"):
            normalize_state_name("   ")

    def test_none_raises_valueerror(self):
        with pytest.raises(ValueError):
            normalize_state_name(None)
