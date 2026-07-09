"""Tests for Job Hunter dashboard routes."""

from __future__ import annotations

from db.database import Database
from worker.hunter_state import HunterState
from worker.sync_server import create_sync_app


def test_dashboard_html_route():
    app = create_sync_app()
    client = app.test_client()
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "Job Hunter Dashboard" in resp.get_data(as_text=True)


def test_hunter_dashboard_api(tmp_path, monkeypatch):
    state = HunterState()
    monkeypatch.setattr("worker.sync_server.hunter_state", state)

    db = Database(tmp_path / "autoapply.db")
    db.save_discovered_job(
        external_id="ext-1",
        platform="linkedin",
        job_title="Python Dev",
        company="Acme",
        location="Remote",
        salary=None,
        apply_url="https://example.com/job/1",
        match_score=72,
        status="pending_sync",
    )
    state.record("found", job_title="Other", company="Co", platform="linkedin")
    state.record("saved", job_title="Python Dev", company="Acme", score=72, job_id=1)
    state.record("cycle", message="1")

    app = create_sync_app(db=db)
    client = app.test_client()
    resp = client.get("/api/hunter/dashboard")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["stats"]["found_total"] == 1
    assert data["stats"]["saved_total"] == 1
    assert data["stats"]["pending_sync"] == 1
    assert len(data["pending_jobs"]) == 1
    assert data["pending_jobs"][0]["job_title"] == "Python Dev"
    assert len(data["activity"]) >= 2
