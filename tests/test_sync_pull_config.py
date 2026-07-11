"""Tests for Mac client shared-config pull."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from config.settings import (
    AppConfig,
    BotConfig,
    SearchCriteria,
    SyncConfig,
    UserProfile,
    save_config,
)
from db.database import Database


@pytest.fixture()
def mac_client(tmp_path, monkeypatch):
    monkeypatch.setattr("config.settings.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("routes.sync.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("app.get_data_dir", lambda: tmp_path)

    cfg = AppConfig(
        profile=UserProfile(
            first_name="Local",
            last_name="User",
            email="local@example.com",
            phone="111",
            city="City",
            state="ST",
            bio="Local bio",
            fallback_resume_path=str(tmp_path / "resume.pdf"),
        ),
        search_criteria=SearchCriteria(
            job_titles=["Old Title"],
            locations=["Old Loc"],
        ),
        bot=BotConfig(min_match_score=90),
        sync=SyncConfig(
            sync_server_url="http://hunter.example:8765",
            sync_token="mac-token",
        ),
    )
    (tmp_path / "resume.pdf").write_text("x")
    (tmp_path / "profile" / "experiences").mkdir(parents=True)
    save_config(cfg)

    test_db = Database(tmp_path / "test.db")
    monkeypatch.setattr("app.db", test_db)
    monkeypatch.setattr("app_state.db", test_db)

    from app import app

    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client, tmp_path


def test_pull_shared_config_merges(mac_client):
    client, tmp_path = mac_client
    remote = {
        "profile": {
            "first_name": "Guilherme",
            "last_name": "Menegatti",
            "email": "g@example.com",
            "phone": "999",
            "city": "SP",
            "state": "SP",
            "bio": "Synced",
            "phone_country_code": "+55",
            "address_line1": "",
            "address_line2": "",
            "zip_code": "",
            "country": "Brazil",
            "linkedin_url": None,
            "portfolio_url": None,
            "screening_answers": {},
            "spoken_languages": [{"code": "pt", "level": "native"}],
        },
        "search_criteria": {
            "job_titles": ["Backend"],
            "locations": ["Remote"],
            "remote_only": True,
            "salary_min": None,
            "keywords_include": [],
            "keywords_exclude": [],
            "experience_levels": ["senior"],
            "job_languages": ["pt", "en"],
        },
        "bot": {
            "enabled_platforms": ["linkedin"],
            "min_match_score": 75,
            "max_applications_per_day": 15,
            "delay_between_applications_seconds": 60,
            "search_interval_seconds": 1800,
            "cover_letter_enabled": True,
        },
    }
    with patch("routes.sync._fetch_remote_shared_config", return_value=remote):
        res = client.post("/api/sync/pull-config")
    assert res.status_code == 200
    assert res.get_json()["success"] is True

    from config.settings import load_config

    cfg = load_config()
    assert cfg.profile.first_name == "Guilherme"
    assert cfg.profile.fallback_resume_path == str(tmp_path / "resume.pdf")
    assert cfg.search_criteria.job_titles == ["Backend"]
    assert cfg.bot.min_match_score == 75
    assert cfg.sync.sync_token == "mac-token"
