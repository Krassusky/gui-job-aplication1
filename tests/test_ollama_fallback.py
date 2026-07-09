"""Unit tests for Ollama provider dispatch and cloud→Ollama fallback."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from config.settings import LLMConfig
from core.ai_engine import (
    _call_llm,
    _should_fallback_to_ollama,
    check_ai_available,
    invoke_llm_with_fallback,
)


class TestOllamaDispatch:
    @patch("core.ai_engine._call_ollama", return_value="local response")
    def test_ollama_dispatch(self, mock_call):
        result = _call_llm("ollama", "", "llama3.2", "hello")
        mock_call.assert_called_once_with("llama3.2", "hello", 120)
        assert result == "local response"

    @patch("core.ai_engine.check_ollama_available", return_value=True)
    def test_check_ai_available_ollama_provider(self, _mock_ping):
        cfg = LLMConfig(provider="ollama", api_key="")
        assert check_ai_available(cfg) is True

    @patch("core.ai_engine.check_ollama_available", return_value=True)
    @patch("core.ai_engine._call_openai_compatible", return_value="cloud")
    def test_invoke_primary_ollama(self, mock_cloud, _mock_ping):
        cfg = LLMConfig(provider="ollama", model="llama3.2")
        with patch("core.ai_engine._call_ollama", return_value="ollama out") as mock_ollama:
            result = invoke_llm_with_fallback("prompt", cfg)
        assert result == "ollama out"
        mock_cloud.assert_not_called()
        mock_ollama.assert_called_once()


class TestFallbackLogic:
    def test_should_fallback_on_429(self):
        assert _should_fallback_to_ollama(RuntimeError("Groq API error (429): rate limit"))

    def test_should_fallback_on_401(self):
        assert _should_fallback_to_ollama(RuntimeError("OpenAI API error (401): bad key"))

    def test_should_not_fallback_on_400(self):
        assert not _should_fallback_to_ollama(RuntimeError("OpenAI API error (400): bad request"))

    def test_should_fallback_on_timeout(self):
        assert _should_fallback_to_ollama(requests.Timeout("timed out"))

    @patch("core.ai_engine.check_ollama_available", return_value=True)
    @patch("core.ai_engine._call_ollama", return_value="fallback text")
    @patch("core.ai_engine._call_openai_compatible", side_effect=RuntimeError("Groq API error (429): limit"))
    def test_invoke_falls_back_to_ollama(self, _mock_cloud, mock_ollama, _mock_ping):
        cfg = LLMConfig(
            provider="groq",
            api_key="gsk-test",
            model="llama-3.3-70b-versatile",
            ollama_fallback_enabled=True,
            ollama_model="llama3.2",
        )
        result = invoke_llm_with_fallback("prompt", cfg)
        assert result == "fallback text"
        mock_ollama.assert_called_once()

    @patch("core.ai_engine.check_ollama_available", return_value=False)
    @patch("core.ai_engine._call_openai_compatible", side_effect=RuntimeError("Groq API error (429): limit"))
    def test_invoke_raises_when_ollama_unreachable(self, _mock_cloud, _mock_ping):
        cfg = LLMConfig(
            provider="groq",
            api_key="gsk-test",
            ollama_fallback_enabled=True,
        )
        with pytest.raises(RuntimeError, match="429"):
            invoke_llm_with_fallback("prompt", cfg)

    @patch("core.ai_engine.check_ollama_available", return_value=True)
    @patch("core.ai_engine._call_ollama", return_value="local only")
    @patch("core.ai_engine._call_openai_compatible")
    def test_no_fallback_when_disabled(self, mock_cloud, mock_ollama, _mock_ping):
        cfg = LLMConfig(
            provider="groq",
            api_key="gsk-test",
            ollama_fallback_enabled=False,
        )
        mock_cloud.side_effect = RuntimeError("Groq API error (429): limit")
        with pytest.raises(RuntimeError, match="429"):
            invoke_llm_with_fallback("prompt", cfg)
        mock_ollama.assert_not_called()

    @patch("core.ai_engine.check_ollama_available", return_value=True)
    @patch("core.ai_engine._call_ollama", return_value="env fallback")
    def test_env_enables_fallback_without_key(self, mock_ollama, _mock_ping, monkeypatch):
        monkeypatch.setenv("AUTOAPPLY_OLLAMA_FALLBACK", "1")
        cfg = LLMConfig(provider="groq", api_key="")
        result = invoke_llm_with_fallback("prompt", cfg)
        assert result == "env fallback"
        mock_ollama.assert_called_once()


class TestSyncDatabase:
    def test_save_discovered_and_ack(self, tmp_path):
        from db.database import Database

        db = Database(tmp_path / "test.db")
        app_id = db.save_discovered_job(
            external_id="job-1",
            platform="linkedin",
            job_title="Engineer",
            company="Acme",
            location="Remote",
            salary=None,
            apply_url="https://example.com/job",
            match_score=88,
            description_text="Great role",
        )
        assert app_id is not None

        jobs = db.get_sync_jobs()
        assert len(jobs) == 1
        assert jobs[0]["job_title"] == "Engineer"

        detail = db.get_sync_job(app_id)
        assert detail["description_text"] == "Great role"

        assert db.ack_sync_job(app_id) is True
        assert db.get_sync_jobs() == []

    def test_duplicate_discovered_job_returns_none(self, tmp_path):
        from db.database import Database

        db = Database(tmp_path / "test.db")
        kwargs = dict(
            external_id="dup-1",
            platform="indeed",
            job_title="Dev",
            company="Co",
            location=None,
            salary=None,
            apply_url="https://example.com",
            match_score=70,
        )
        assert db.save_discovered_job(**kwargs) is not None
        assert db.save_discovered_job(**kwargs) is None


class TestSyncAPI:
    def test_sync_endpoints_require_token(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AUTOAPPLY_SYNC_TOKEN", "secret-token")
        from db.database import Database
        from worker.sync_server import create_sync_app

        db = Database(tmp_path / "sync.db")
        app = create_sync_app(db)
        client = app.test_client()

        assert client.get("/api/sync/jobs").status_code == 401

        headers = {"Authorization": "Bearer secret-token"}
        resp = client.get("/api/sync/jobs", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["count"] == 0

    def test_sync_list_ack_flow(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AUTOAPPLY_SYNC_TOKEN", "tok")
        from db.database import Database
        from worker.sync_server import create_sync_app

        db = Database(tmp_path / "sync.db")
        job_id = db.save_discovered_job(
            external_id="x1",
            platform="linkedin",
            job_title="PM",
            company="Beta",
            location="NY",
            salary=None,
            apply_url="https://example.com/x",
            match_score=80,
            description_text="desc",
        )
        app = create_sync_app(db)
        client = app.test_client()
        headers = {"Authorization": "Bearer tok"}

        listed = client.get("/api/sync/jobs", headers=headers).get_json()
        assert listed["count"] == 1

        detail = client.get(f"/api/sync/jobs/{job_id}", headers=headers).get_json()
        assert detail["description_text"] == "desc"

        ack = client.post(f"/api/sync/jobs/{job_id}/ack", headers=headers)
        assert ack.status_code == 200
        assert client.get("/api/sync/jobs", headers=headers).get_json()["count"] == 0
