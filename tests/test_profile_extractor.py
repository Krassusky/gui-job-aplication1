"""Tests for profile extraction from CV/LinkedIn text."""

from unittest.mock import MagicMock, patch

import pytest

from core.profile_extractor import (
    extract_profile_from_text,
    merge_extracted_into_config,
    save_experience_text,
)

SAMPLE_LLM_RESPONSE = """{
  "profile": {
    "first_name": "Jane",
    "last_name": "Doe",
    "email": "jane@example.com",
    "phone_country_code": "+1",
    "phone": "5551234567",
    "city": "Austin",
    "state": "TX",
    "country": "United States",
    "bio": "Software engineer with 8 years of experience.",
    "linkedin_url": "https://linkedin.com/in/janedoe",
    "portfolio_url": ""
  },
  "search_criteria": {
    "job_titles": ["Software Engineer", "Backend Developer"],
    "keywords_include": ["Python", "Flask"],
    "experience_levels": ["senior"]
  },
  "screening_answers": {
    "years_experience": "8"
  },
  "experience_text": "- Built APIs at Acme Corp"
}"""


class TestExtractProfileFromText:
    @patch("core.ai_engine.invoke_llm", return_value=SAMPLE_LLM_RESPONSE)
    def test_extracts_structured_profile(self, mock_llm):
        result = extract_profile_from_text("Jane Doe resume text", MagicMock())
        assert result["profile"]["first_name"] == "Jane"
        assert result["profile"]["email"] == "jane@example.com"
        assert "Python" in result["search_criteria"]["keywords_include"]
        mock_llm.assert_called_once()

    def test_empty_text_raises(self):
        with pytest.raises(ValueError, match="empty"):
            extract_profile_from_text("  ", MagicMock())


class TestMergeExtractedIntoConfig:
    def test_merges_empty_fields_only(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config.settings.get_data_dir", lambda: tmp_path)

        from config.settings import AppConfig

        data = {
            "profile": {
                "first_name": "Old",
                "last_name": "Name",
                "email": "old@example.com",
                "phone": "111",
                "city": "X",
                "state": "Y",
                "bio": "bio",
            },
            "search_criteria": {"job_titles": ["Dev"], "locations": ["Remote"]},
        }
        cfg = AppConfig(**data)
        extracted = {
            "profile": {
                "first_name": "Jane",
                "last_name": "Doe",
                "linkedin_url": "https://linkedin.com/in/jane",
            },
            "search_criteria": {
                "keywords_include": ["Python"],
            },
        }

        applied = merge_extracted_into_config(cfg, extracted)
        assert cfg.profile.first_name == "Old"
        assert cfg.profile.linkedin_url == "https://linkedin.com/in/jane"
        assert "linkedin_url" in applied["profile"]
        assert "keywords_include" in applied["search_criteria"]


class TestSaveExperienceText:
    def test_writes_experience_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config.settings.get_data_dir", lambda: tmp_path)
        name = save_experience_text("- Did things\n- More things", "imported_cv.txt")
        assert name == "imported_cv.txt"
        content = (tmp_path / "profile" / "experiences" / "imported_cv.txt").read_text()
        assert "Did things" in content
