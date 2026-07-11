"""Tests for hunter login and shared config sync API."""

from __future__ import annotations

import json

import pytest

from config.settings import (
    AppConfig,
    BotConfig,
    SearchCriteria,
    UserProfile,
    save_config,
)
from db.database import Database
from worker.hunter_auth import (
    extract_shared_config,
    hash_password,
    merge_shared_config,
    save_password,
    verify_password,
)
from worker.sync_server import create_sync_app


def _sample_config(**overrides) -> AppConfig:
    data = dict(
        profile=UserProfile(
            first_name="Gui",
            last_name="Menegatti",
            email="gui@example.com",
            phone="5551234",
            city="São Paulo",
            state="SP",
            bio="Engineer",
        ),
        search_criteria=SearchCriteria(
            job_titles=["Software Engineer"],
            locations=["Remote"],
            remote_only=True,
            keywords_include=["Python"],
            experience_levels=["mid", "senior"],
            job_languages=["pt", "en"],
        ),
        bot=BotConfig(min_match_score=80, search_interval_seconds=900),
    )
    data.update(overrides)
    return AppConfig(**data)


@pytest.fixture()
def auth_env(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOAPPLY_SYNC_TOKEN", "sync-secret")
    monkeypatch.setenv("AUTOAPPLY_HUNTER_USER", "hunter")
    monkeypatch.setenv("AUTOAPPLY_HUNTER_PASSWORD_HASH", hash_password("s3cret"))
    monkeypatch.setattr("config.settings.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("worker.sync_server.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("worker.hunter_auth.get_data_dir", lambda: tmp_path)
    cfg = _sample_config()
    save_config(cfg)
    db = Database(tmp_path / "t.db")
    app = create_sync_app(db)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client, tmp_path


class TestHunterAuthHelpers:
    def test_verify_password_hash(self, tmp_path, monkeypatch):
        monkeypatch.setattr("worker.hunter_auth.get_data_dir", lambda: tmp_path)
        save_password("admin", "hunter-pass")
        assert verify_password("admin", "hunter-pass")
        assert not verify_password("admin", "wrong")
        assert not verify_password("other", "hunter-pass")


class TestHunterLogin:
    def test_login_logout_session(self, auth_env):
        client, _ = auth_env
        bad = client.post(
            "/api/hunter/login",
            json={"username": "hunter", "password": "nope"},
        )
        assert bad.status_code == 401

        ok = client.post(
            "/api/hunter/login",
            json={"username": "hunter", "password": "s3cret"},
        )
        assert ok.status_code == 200
        sess = client.get("/api/hunter/session")
        assert sess.get_json()["authenticated"] is True

        dash = client.get("/api/hunter/dashboard")
        assert dash.status_code == 200

        client.post("/api/hunter/logout")
        assert client.get("/api/hunter/dashboard").status_code == 401

    def test_login_with_sync_token(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AUTOAPPLY_SYNC_TOKEN", "sync-secret")
        monkeypatch.delenv("AUTOAPPLY_HUNTER_PASSWORD", raising=False)
        monkeypatch.delenv("AUTOAPPLY_HUNTER_PASSWORD_HASH", raising=False)
        monkeypatch.setattr("config.settings.get_data_dir", lambda: tmp_path)
        monkeypatch.setattr("worker.sync_server.get_data_dir", lambda: tmp_path)
        monkeypatch.setattr("worker.hunter_auth.get_data_dir", lambda: tmp_path)
        save_config(_sample_config())
        app = create_sync_app(Database(tmp_path / "t.db"))
        app.config["TESTING"] = True
        client = app.test_client()
        res = client.post("/api/hunter/login", json={"token": "sync-secret"})
        assert res.status_code == 200
        assert client.get("/api/hunter/dashboard").status_code == 200


class TestSharedConfigAPI:
    def test_sync_config_requires_bearer(self, auth_env):
        client, _ = auth_env
        assert client.get("/api/sync/config").status_code == 401

    def test_get_and_put_sync_config(self, auth_env):
        client, tmp_path = auth_env
        headers = {"Authorization": "Bearer sync-secret"}
        res = client.get("/api/sync/config", headers=headers)
        assert res.status_code == 200
        data = res.get_json()
        assert data["profile"]["first_name"] == "Gui"
        assert data["search_criteria"]["job_titles"] == ["Software Engineer"]
        assert data["bot"]["min_match_score"] == 80
        assert "api_key" not in json.dumps(data)

        put = client.put(
            "/api/sync/config",
            headers=headers,
            json={
                "profile": {"first_name": "Guilherme", "bio": "Updated"},
                "search_criteria": {"job_titles": ["Backend Engineer"], "locations": ["Remote"]},
                "bot": {"min_match_score": 70},
            },
        )
        assert put.status_code == 200
        body = put.get_json()
        assert body["config"]["profile"]["first_name"] == "Guilherme"
        assert body["config"]["search_criteria"]["job_titles"] == ["Backend Engineer"]
        assert body["config"]["bot"]["min_match_score"] == 70

        # Persisted
        from config.settings import load_config

        cfg = load_config()
        assert cfg.profile.first_name == "Guilherme"
        assert cfg.profile.last_name == "Menegatti"  # untouched
        assert cfg.bot.min_match_score == 70

    def test_hunter_config_via_session(self, auth_env):
        client, _ = auth_env
        client.post(
            "/api/hunter/login",
            json={"username": "hunter", "password": "s3cret"},
        )
        res = client.get("/api/hunter/config")
        assert res.status_code == 200
        assert res.get_json()["profile"]["email"] == "gui@example.com"

    def test_merge_shared_preserves_local_only(self):
        cfg = _sample_config()
        cfg.llm.api_key = "sk-secret"
        cfg.profile.fallback_resume_path = "/local/resume.pdf"
        merge_shared_config(
            cfg,
            {
                "profile": {"first_name": "X", "fallback_resume_path": "/evil"},
                "bot": {"min_match_score": 50, "apply_mode": "full_auto"},
            },
        )
        assert cfg.profile.first_name == "X"
        assert cfg.profile.fallback_resume_path == "/local/resume.pdf"
        assert cfg.bot.min_match_score == 50
        assert cfg.bot.apply_mode == "review"  # not in SHARED_BOT_KEYS
        assert cfg.llm.api_key == "sk-secret"
        shared = extract_shared_config(cfg)
        assert "fallback_resume_path" not in shared["profile"]
