"""Tests for PDF triage utility.

Tests that require actual PDF files are skipped if files are not present
(they are gitignored in data/raw/ and docs/).
"""

from pathlib import Path

import pytest

RMK13_FULL = Path("docs/policy_documents/rmk13/Full_Document_RMK13.pdf")
DOE_2024 = Path("data/raw/doe/doe_eqr_2024.pdf")

skip_no_rmk13 = pytest.mark.skipif(
    not RMK13_FULL.exists(), reason="RMK13 PDF not present"
)
skip_no_doe = pytest.mark.skipif(
    not DOE_2024.exists(), reason="DOE EQR PDF not present"
)


class TestModuleImports:
    def test_imports_cleanly(self):
        import src.ingestion.pdf_triage  # noqa: F401

    def test_entry_points_exist(self):
        from src.ingestion.pdf_triage import triage_pdf, load_keyword_sets
        assert callable(triage_pdf)
        assert callable(load_keyword_sets)


class TestKeywordSets:
    def test_load_keyword_sets(self):
        from src.ingestion.pdf_triage import load_keyword_sets
        sets = load_keyword_sets()
        assert isinstance(sets, dict)
        assert len(sets) >= 7
        assert "tourism_policy_commitments" in sets
        assert "rmk13_tourism" in sets

    def test_all_sets_have_keywords(self):
        from src.ingestion.pdf_triage import load_keyword_sets
        sets = load_keyword_sets()
        for name, keywords in sets.items():
            assert isinstance(keywords, list), f"{name} is not a list"
            assert len(keywords) >= 3, f"{name} has fewer than 3 keywords"


class TestSnippetExtraction:
    def test_extract_snippet(self):
        from src.ingestion.pdf_triage import _extract_snippet
        text = "This document targets 15 million visitors by 2030."
        snippet = _extract_snippet(text, "targets")
        assert "targets" in snippet.lower()

    def test_extract_snippet_not_found(self):
        from src.ingestion.pdf_triage import _extract_snippet
        snippet = _extract_snippet("Hello world", "nonexistent")
        assert snippet == ""


class TestKeywordSearch:
    def test_search_keywords(self):
        from src.ingestion.pdf_triage import _search_keywords
        text = "Tourism receipts increased. The target for 2030 is ambitious."
        matched = _search_keywords(text, ["target", "receipts", "missing"])
        assert "target" in matched
        assert "receipts" in matched
        assert "missing" not in matched

    def test_case_insensitive(self):
        from src.ingestion.pdf_triage import _search_keywords
        matched = _search_keywords("TOURISM TARGET", ["tourism", "target"])
        assert len(matched) == 2


@skip_no_rmk13
class TestTriagePDF:
    def test_rmk13_text_extractable(self):
        from src.ingestion.pdf_triage import triage_pdf, load_keyword_sets
        sets = load_keyword_sets()
        result = triage_pdf(RMK13_FULL, {"rmk13_tourism": sets["rmk13_tourism"]}, min_keyword_hits=1)
        assert result["text_extractable"] is True
        assert result["total_pages"] > 100

    def test_rmk13_finds_target_pages(self):
        from src.ingestion.pdf_triage import triage_pdf, load_keyword_sets
        sets = load_keyword_sets()
        result = triage_pdf(RMK13_FULL, {"rmk13_tourism": sets["rmk13_tourism"]}, min_keyword_hits=1)
        assert result["estimated_target_pages_total"] > 0
        assert result["estimated_target_pages_total"] < result["total_pages"]

    def test_rmk13_has_recommendation(self):
        from src.ingestion.pdf_triage import triage_pdf, load_keyword_sets
        sets = load_keyword_sets()
        result = triage_pdf(RMK13_FULL, sets, min_keyword_hits=2)
        assert result["extraction_recommendation"] in (
            "deterministic", "llm", "mixed", "manual_review"
        )

    def test_token_savings_above_threshold(self):
        from src.ingestion.pdf_triage import triage_pdf, load_keyword_sets
        sets = load_keyword_sets()
        rmk_sets = {k: v for k, v in sets.items() if k in ("rmk13_tourism", "tourism_policy_commitments")}
        result = triage_pdf(RMK13_FULL, rmk_sets, min_keyword_hits=2)
        full_tokens = result["total_pages"] * 500
        savings_pct = (1 - result["estimated_llm_tokens_if_extracted"] / full_tokens) * 100
        assert savings_pct > 70

    def test_likely_toc_field_present(self):
        from src.ingestion.pdf_triage import triage_pdf, load_keyword_sets
        sets = load_keyword_sets()
        result = triage_pdf(RMK13_FULL, sets, min_keyword_hits=2)
        for topic, pages in result["target_pages_by_topic"].items():
            for page in pages:
                assert "likely_toc" in page

    def test_substantive_count_present(self):
        from src.ingestion.pdf_triage import triage_pdf, load_keyword_sets
        sets = load_keyword_sets()
        result = triage_pdf(RMK13_FULL, sets, min_keyword_hits=2)
        assert "substantive_target_pages_total" in result
        assert "toc_pages_excluded" in result
        assert result["substantive_target_pages_total"] <= result["estimated_target_pages_total"]


@skip_no_doe
class TestDOETriagePDF:
    def test_doe_water_quality_keywords(self):
        from src.ingestion.pdf_triage import triage_pdf, load_keyword_sets
        sets = load_keyword_sets()
        result = triage_pdf(DOE_2024, {"water_quality": sets["water_quality"]}, min_keyword_hits=2)
        assert result["text_extractable"] is True
        assert result["estimated_target_pages_total"] > 0


class TestEmptyPDF:
    def test_nonexistent_pdf(self):
        from src.ingestion.pdf_triage import triage_pdf
        result = triage_pdf(Path("nonexistent.pdf"), {"test": ["keyword"]})
        assert result["text_extractable"] is False
        assert result["total_pages"] == 0
