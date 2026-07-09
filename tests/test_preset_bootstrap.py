"""Tests for bundled preset bootstrap (Guilherme Mac edition)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from config.settings import get_data_dir, load_config
from presets import bootstrap


@pytest.fixture
def preset_tree(tmp_path, monkeypatch):
    """Minimal guilherme-like preset in a fake project root."""
    preset_id = "guilherme-menegatti"
    preset_dir = tmp_path / "presets" / preset_id
    experiences = preset_dir / "profile" / "experiences"
    experiences.mkdir(parents=True)
    (experiences / "summary.txt").write_text("Transformation leader", encoding="utf-8")
    (preset_dir / "default_resume.docx").write_bytes(b"fake-docx")
    (preset_dir / "secrets.env").write_text("GROQ_API_KEY=test-key-123\n", encoding="utf-8")
    (preset_dir / "config.template.json").write_text(
        json.dumps(
            {
                "profile": {
                    "first_name": "Guilherme",
                    "last_name": "Menegatti",
                    "email": "menegattigui@gmail.com",
                    "phone_country_code": "+52",
                    "phone": "5587964486",
                    "city": "Mexico City",
                    "state": "CDMX",
                    "country": "Mexico",
                    "bio": "Transformation Manager",
                    "linkedin_url": "https://www.linkedin.com/in/guilhermemenegatti/",
                    "fallback_resume_path": "__AUTOAPPLY_DIR__/default_resume.docx",
                },
                "search_criteria": {
                    "job_titles": ["Transformation Manager"],
                    "locations": ["Mexico City, Mexico"],
                },
                "bot": {"enabled_platforms": ["linkedin"], "min_match_score": 75},
                "llm": {
                    "provider": "groq",
                    "api_key": "__GROQ_API_KEY__",
                    "model": "llama-3.3-70b-versatile",
                    "providers": [
                        {
                            "id": "abc",
                            "label": "Groq",
                            "provider": "groq",
                            "api_key": "__GROQ_API_KEY__",
                            "model": "llama-3.3-70b-versatile",
                        }
                    ],
                    "active_id": "abc",
                },
                "version": "2.0",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "presets" / ".active_preset").write_text(preset_id, encoding="utf-8")
    monkeypatch.setattr(bootstrap, "_project_root", lambda: tmp_path)
    monkeypatch.setattr("config.settings.get_data_dir", lambda: tmp_path / "data")
    return preset_dir


def test_install_preset_writes_config_and_resume(preset_tree):
    installed = bootstrap.install_preset(preset_tree, force=True)
    assert installed is True

    config = load_config()
    assert config is not None
    assert config.profile.email == "menegattigui@gmail.com"
    assert config.llm.api_key == "test-key-123"
    assert (get_data_dir() / "default_resume.docx").exists()
    assert (get_data_dir() / "profile" / "experiences" / "summary.txt").exists()


def test_apply_bundled_preset_skips_when_marker_present(preset_tree):
    bootstrap.install_preset(preset_tree, force=True)
    assert bootstrap.apply_bundled_preset_if_needed() is False


def test_get_active_bundled_preset_id(preset_tree):
    assert bootstrap.get_active_bundled_preset_id() == "guilherme-menegatti"
