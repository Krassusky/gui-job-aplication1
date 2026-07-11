"""Tests for Job Hunter thermal guards and start/stop control."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from worker import thermal
from worker.hunter_state import HunterState
from worker.sync_server import create_sync_app
from worker.thermal import SensorSnapshot, is_cool_enough, is_too_hot


class TestThermal:
    def test_too_hot_cpu(self):
        assert is_too_hot(SensorSnapshot(cpu_c=80, smc_c=50, fan_rpm=1000))

    def test_too_hot_fan(self):
        assert is_too_hot(SensorSnapshot(cpu_c=50, smc_c=50, fan_rpm=3000))

    def test_cool_enough(self):
        assert is_cool_enough(SensorSnapshot(cpu_c=60, smc_c=60, fan_rpm=1500))

    def test_no_sensors_not_blocking(self):
        assert not is_too_hot(SensorSnapshot())
        assert is_cool_enough(SensorSnapshot())

    def test_read_sensors_parses_output(self, monkeypatch):
        sample = """
coretemp-isa-0000
Package id 0:  +71.0°C
applesmc-isa-0300
TC0p:         +68.0°C
Main :        1800 RPM
"""
        monkeypatch.setattr(
            thermal.subprocess,
            "check_output",
            lambda *a, **k: sample,
        )
        snap = thermal.read_sensors()
        assert snap.cpu_c == 71
        assert snap.smc_c == 68
        assert snap.fan_rpm == 1800


class TestHunterControl:
    def test_request_start_stop(self, tmp_path, monkeypatch):
        state = HunterState()

        class FakeCfg:
            pass

        state.configure(config_loader=lambda: FakeCfg(), db=object())

        started = []

        def fake_loop(loader, db):
            started.append(True)
            # Exit quickly
            state._want_running = False

        monkeypatch.setattr("worker.job_hunter.hunt_loop", fake_loop)
        result = state.request_start()
        assert result["ok"] is True
        # Give thread a moment
        import time

        time.sleep(0.2)
        assert started
        stop = state.request_stop()
        assert stop["ok"] is True


@pytest.fixture()
def sync_client(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOAPPLY_SYNC_TOKEN", "test-token-xyz")
    from db.database import Database

    db = Database(tmp_path / "t.db")
    app = create_sync_app(db)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestHunterControlAPI:
    def test_start_requires_auth(self, sync_client):
        res = sync_client.post("/api/hunter/start")
        assert res.status_code == 401

    def test_start_with_token(self, sync_client, monkeypatch):
        monkeypatch.setattr(
            "worker.hunter_state.hunter_state.request_start",
            lambda: {"ok": True, "run_state": "running"},
        )
        res = sync_client.post(
            "/api/hunter/start",
            headers={"Authorization": "Bearer test-token-xyz"},
        )
        assert res.status_code == 200
        assert res.get_json()["ok"] is True

    def test_status_and_dashboard_include_run_state(self, sync_client, monkeypatch):
        monkeypatch.setattr(
            "worker.sync_server.read_sensors",
            lambda: SensorSnapshot(cpu_c=55, smc_c=50, fan_rpm=1000),
        )
        res = sync_client.get("/api/hunter/status")
        assert res.status_code == 200
        data = res.get_json()
        assert "run_state" in data
        assert data["sensors"]["cpu_c"] == 55

        dash = sync_client.get(
            "/api/hunter/dashboard",
            headers={"Authorization": "Bearer test-token-xyz"},
        )
        assert dash.status_code == 200
        body = dash.get_json()
        assert "stats" in body
        assert body["sensors"]["cpu_c"] == 55

    def test_health_includes_run_state(self, sync_client, monkeypatch):
        monkeypatch.setattr(
            "worker.sync_server.read_sensors",
            lambda: SensorSnapshot(cpu_c=40),
        )
        res = sync_client.get("/api/sync/health")
        assert res.status_code == 200
        assert res.get_json()["status"] == "ok"
        assert "run_state" in res.get_json()
