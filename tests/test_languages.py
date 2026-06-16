"""Tests for language helpers."""

from core.languages import (
    DEFAULT_JOB_LANGUAGES,
    expand_search_titles,
    format_languages_line,
    score_language_match,
)


class TestLanguages:
    def test_format_languages_line(self):
        spoken = [
            {"code": "pt", "level": "native"},
            {"code": "en", "level": "fluent"},
            {"code": "es", "level": "fluent"},
        ]
        line = format_languages_line(spoken, "pt")
        assert "Português" in line
        assert "Inglês" in line
        assert "Espanhol" in line

    def test_expand_search_titles(self):
        titles = expand_search_titles("Software Engineer", DEFAULT_JOB_LANGUAGES)
        assert "Software Engineer" in titles
        assert len(titles) > 1

    def test_score_language_match(self):
        desc = "Bilingual role requiring fluent English and Spanish."
        score = score_language_match(desc, ["en", "es"])
        assert score > 0
