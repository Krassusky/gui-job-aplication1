"""Tests for profile import routes."""

from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def _locale_en():
    from core.i18n import set_locale

    set_locale("en")
    yield
    set_locale("pt")


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    monkeypatch.setattr("config.settings.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("app.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("routes.profile.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("routes.login.get_data_dir", lambda: tmp_path)

    (tmp_path / "profile" / "experiences").mkdir(parents=True)
    minimal_config = {
        "profile": {
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "phone": "555-0100",
            "city": "Remote",
            "state": "",
            "bio": "Test bio",
        },
        "search_criteria": {"job_titles": ["Engineer"], "locations": ["Remote"]},
        "bot": {"enabled_platforms": ["linkedin"]},
        "llm": {"provider": "", "api_key": "", "model": ""},
    }
    (tmp_path / "config.json").write_text(json.dumps(minimal_config), encoding="utf-8")

    import app as app_module

    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def test_import_linkedin_requires_ai(app_client):
    rv = app_client.post("/api/profile/import-linkedin", json={"apply": False})
    assert rv.status_code == 400
    assert "AI provider" in rv.get_json()["error"]
