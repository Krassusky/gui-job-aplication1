"""Unit tests for login browser API endpoints.

Requirement traceability:
    FR-068  Platform login browser endpoints
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from db.database import Database


@pytest.fixture(autouse=True)
def _locale_en():
    from core.i18n import set_locale

    set_locale("en")
    yield
    set_locale("pt")


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    """Yield (test_client, tmp_path) with paths redirected to tmp_path."""
    monkeypatch.setattr("config.settings.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("core.browser_engine.get_data_dir", lambda: tmp_path)
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
    }
    (tmp_path / "config.json").write_text(json.dumps(minimal_config), encoding="utf-8")

    test_db = Database(tmp_path / "test.db")
    monkeypatch.setattr("app.db", test_db)
    monkeypatch.setattr("app_state.db", test_db)

    import app as app_module

    # Reset login state between tests
    monkeypatch.setattr(app_module, "_login_proc", None)
    monkeypatch.setattr("app_state.login_proc", None)
    monkeypatch.setattr("app_state.login_playwright", None)
    monkeypatch.setattr("app_state.login_context", None)
    monkeypatch.setattr("app_state.login_engine", "chromium")

    app_module.app.config["TESTING"] = True
    return app_module.app.test_client(), tmp_path


class TestLoginOpen:
    """POST /api/login/open — opens system Chrome for platform login."""

    def test_missing_url_returns_400(self, app_client):
        client, _ = app_client
        rv = client.post("/api/login/open", json={})
        assert rv.status_code == 400
        assert "url" in rv.get_json()["error"]

    def test_no_body_returns_400(self, app_client):
        client, _ = app_client
        rv = client.post(
            "/api/login/open",
            data="",
            content_type="application/json",
        )
        assert rv.status_code == 400

    def test_disallowed_domain_returns_400(self, app_client):
        client, _ = app_client
        rv = client.post("/api/login/open", json={"url": "https://evil.com/login"})
        assert rv.status_code == 400
        assert "Only LinkedIn and Indeed" in rv.get_json()["error"]

    @patch("routes.login._open_playwright_login", return_value="opening")
    @patch("routes.login.find_system_chrome", return_value=None)
    def test_no_chrome_uses_webkit_fallback(self, _mock, mock_webkit, app_client):
        client, _ = app_client
        rv = client.post(
            "/api/login/open",
            json={"url": "https://www.linkedin.com/login"},
        )
        assert rv.status_code == 200
        assert rv.get_json()["status"] == "opening"
        mock_webkit.assert_called_once()

    @patch("routes.login.preferred_engine", return_value="webkit")
    @patch("routes.login._open_playwright_login", return_value="opening")
    @patch("routes.login.find_system_chrome", return_value="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    def test_macos_uses_playwright_even_with_chrome(
        self, _chrome, mock_pw, _engine, app_client
    ):
        """On macOS preferred_engine is webkit — login must use Playwright, not Chrome."""
        client, _ = app_client
        rv = client.post(
            "/api/login/open",
            json={"url": "https://www.linkedin.com/login"},
        )
        assert rv.status_code == 200
        assert rv.get_json()["status"] == "opening"
        mock_pw.assert_called_once_with("https://www.linkedin.com/login", "webkit")

    @patch("routes.login._profile_chrome_running", return_value=False)
    @patch("routes.login.subprocess.Popen")
    @patch("routes.login.find_system_chrome", return_value="C:/chrome.exe")
    def test_valid_linkedin_url_returns_opening(self, _chrome, mock_popen, _profile, app_client):
        client, _ = app_client
        mock_popen.return_value = MagicMock(pid=1234)
        rv = client.post(
            "/api/login/open",
            json={"url": "https://www.linkedin.com/login"},
        )
        assert rv.status_code == 200
        assert rv.get_json()["status"] == "opening"
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert "--remote-debugging-port=0" in args
        assert "--new-window" not in args

    @patch("routes.login._profile_chrome_running", return_value=False)
    @patch("routes.login.subprocess.Popen")
    @patch("routes.login.find_system_chrome", return_value="C:/chrome.exe")
    def test_valid_indeed_url_returns_opening(self, _chrome, mock_popen, _profile, app_client):
        client, _ = app_client
        mock_popen.return_value = MagicMock(pid=1234)
        rv = client.post(
            "/api/login/open",
            json={"url": "https://secure.indeed.com/auth"},
        )
        assert rv.status_code == 200
        assert rv.get_json()["status"] == "opening"

    @patch("routes.login._cdp_reachable", return_value=True)
    @patch("routes.login._get_cdp_port", return_value=9222)
    @patch("routes.login.subprocess.Popen")
    @patch("routes.login.find_system_chrome", return_value="C:/chrome.exe")
    def test_already_open_reuses_browser(self, _chrome, mock_popen, _port, _cdp, app_client, monkeypatch):
        """If a browser is already open, navigate without terminating."""
        client, _ = app_client
        fake_proc = MagicMock()
        fake_proc.poll.return_value = None
        monkeypatch.setattr("app_state.login_proc", fake_proc)

        mock_popen.return_value = MagicMock(pid=5678)
        rv = client.post(
            "/api/login/open",
            json={"url": "https://secure.indeed.com/auth"},
        )
        assert rv.status_code == 200
        assert rv.get_json()["status"] == "navigated"
        fake_proc.terminate.assert_not_called()
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert "--new-window" not in args


class TestLoginClose:
    """POST /api/login/close — closes the login browser."""

    def test_close_when_not_open_returns_already_closed(self, app_client):
        client, _ = app_client
        rv = client.post("/api/login/close")
        assert rv.status_code == 200
        assert rv.get_json()["status"] == "already_closed"

    def test_close_when_open_terminates_process(self, app_client, monkeypatch):
        client, _ = app_client
        import app as app_module

        fake_proc = MagicMock()
        fake_proc.poll.return_value = None
        monkeypatch.setattr(app_module, "_login_proc", fake_proc)
        monkeypatch.setattr("app_state.login_proc", fake_proc)
        rv = client.post("/api/login/close")
        assert rv.status_code == 200
        assert rv.get_json()["status"] == "closed"
        fake_proc.terminate.assert_called_once()
        import app_state
        assert app_state.login_proc is None


class TestLoginStatus:
    """GET /api/login/status — reports whether a login browser is open."""

    def test_status_when_closed(self, app_client):
        client, _ = app_client
        rv = client.get("/api/login/status")
        assert rv.status_code == 200
        assert rv.get_json()["open"] is False

    def test_status_when_running(self, app_client, monkeypatch):
        client, _ = app_client
        import app as app_module

        fake_proc = MagicMock()
        fake_proc.poll.return_value = None  # still running
        monkeypatch.setattr(app_module, "_login_proc", fake_proc)
        monkeypatch.setattr("app_state.login_proc", fake_proc)
        rv = client.get("/api/login/status")
        assert rv.status_code == 200
        assert rv.get_json()["open"] is True

    def test_status_exited_process_auto_cleans(self, app_client, monkeypatch):
        """If Chrome process exited, status returns false and cleans up."""
        client, _ = app_client
        import app as app_module

        fake_proc = MagicMock()
        fake_proc.poll.return_value = 0  # process exited
        monkeypatch.setattr(app_module, "_login_proc", fake_proc)
        monkeypatch.setattr("app_state.login_proc", fake_proc)
        rv = client.get("/api/login/status")
        assert rv.status_code == 200
        assert rv.get_json()["open"] is False
        import app_state
        assert app_state.login_proc is None


# ===================================================================
# find_system_chrome (core/browser_engine.py)
# ===================================================================


class TestLoginFindSystemChrome:
    """Platform-specific Chrome detection."""

    @patch("platform.system", return_value="Windows")
    @patch("core.browser_engine.os.path.isfile", return_value=False)
    def test_windows_no_chrome(self, mock_isfile, mock_sys):
        from core.browser_engine import find_system_chrome
        assert find_system_chrome() is None

    @patch("platform.system", return_value="Windows")
    @patch("core.browser_engine.os.path.isfile")
    def test_windows_chrome_found(self, mock_isfile, mock_sys):
        from core.browser_engine import find_system_chrome
        mock_isfile.side_effect = lambda p: "chrome.exe" in p.lower()
        result = find_system_chrome()
        assert result is not None
        assert "chrome.exe" in result.lower()

    @patch("platform.system", return_value="Darwin")
    @patch("core.browser_engine.os.path.isfile", return_value=True)
    def test_darwin_chrome_found(self, mock_isfile, mock_sys):
        from core.browser_engine import find_system_chrome
        result = find_system_chrome()
        assert "Google Chrome" in result

    @patch("platform.system", return_value="Linux")
    @patch("core.browser_engine.os.path.isfile", return_value=False)
    def test_linux_no_chrome(self, mock_isfile, mock_sys):
        from core.browser_engine import find_system_chrome
        assert find_system_chrome() is None


# ===================================================================
# login_open — error paths
# ===================================================================


class TestLoginOpenErrors:
    """Error paths in POST /api/login/open."""

    @patch("routes.login._profile_chrome_running", return_value=False)
    @patch("routes.login.subprocess.Popen", side_effect=OSError("Permission denied"))
    @patch("routes.login.find_system_chrome", return_value="C:/chrome.exe")
    def test_popen_failure_returns_500(self, _chrome, _popen, _profile, app_client):
        client, _ = app_client
        rv = client.post("/api/login/open", json={"url": "https://www.linkedin.com/login"})
        assert rv.status_code == 500
        assert "Failed to open browser" in rv.get_json()["error"]

    @patch("routes.login._profile_chrome_running", return_value=False)
    @patch("routes.login.subprocess.Popen")
    @patch("routes.login.find_system_chrome", return_value="C:/chrome.exe")
    def test_stale_proc_clears_before_open(self, _chrome, mock_popen, _profile, app_client, monkeypatch):
        """Exited login proc is cleared and a fresh browser is opened."""
        client, _ = app_client
        old_proc = MagicMock()
        old_proc.poll.return_value = 0
        monkeypatch.setattr("app_state.login_proc", old_proc)

        mock_popen.return_value = MagicMock(pid=999)
        rv = client.post("/api/login/open", json={"url": "https://www.linkedin.com/login"})
        assert rv.status_code == 200
        assert rv.get_json()["status"] == "opening"
        old_proc.terminate.assert_not_called()


# ===================================================================
# login_close — terminate exception
# ===================================================================


class TestLoginCloseErrors:
    """Error paths in POST /api/login/close."""

    def test_close_terminate_exception_handled(self, app_client, monkeypatch):
        client, _ = app_client
        fake_proc = MagicMock()
        fake_proc.poll.return_value = None
        fake_proc.terminate.side_effect = OSError("already dead")
        monkeypatch.setattr("app_state.login_proc", fake_proc)
        rv = client.post("/api/login/close")
        assert rv.status_code == 200
        assert rv.get_json()["status"] == "closed"


# ===================================================================
# login_sessions
# ===================================================================


class TestLoginSessions:
    """GET /api/login/sessions — cookie-based session detection."""

    def test_no_cookies_file(self, app_client):
        """When no cookies DB exists, returns all false."""
        client, _ = app_client
        rv = client.get("/api/login/sessions")
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["linkedin"] is False
        assert data["indeed"] is False

    def test_with_cookies_db(self, app_client):
        """When cookies DB has LinkedIn session cookie, returns linkedin=True."""
        client, tmp_path = app_client
        import sqlite3

        cookies_dir = tmp_path / "browser_profile" / "Default" / "Network"
        cookies_dir.mkdir(parents=True)
        cookies_db = cookies_dir / "Cookies"

        conn = sqlite3.connect(str(cookies_db))
        conn.execute(
            "CREATE TABLE cookies (host_key TEXT, name TEXT, value TEXT, "
            "path TEXT, expires_utc INTEGER, is_secure INTEGER, is_httponly INTEGER, "
            "last_access_utc INTEGER, has_expires INTEGER, is_persistent INTEGER, "
            "priority INTEGER, encrypted_value BLOB, samesite INTEGER, "
            "source_scheme INTEGER, source_port INTEGER, last_update_utc INTEGER)"
        )
        conn.execute(
            "INSERT INTO cookies (host_key, name, value) VALUES (?, ?, ?)",
            (".linkedin.com", "li_at", "session_token"),
        )
        conn.commit()
        conn.close()

        rv = client.get("/api/login/sessions")
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["linkedin"] is True
        assert data["indeed"] is False

    def test_cookies_db_error_handled(self, app_client):
        """Corrupted cookies DB is handled gracefully."""
        client, tmp_path = app_client

        cookies_dir = tmp_path / "browser_profile" / "Default" / "Network"
        cookies_dir.mkdir(parents=True)
        # Write garbage to the cookies file
        (cookies_dir / "Cookies").write_bytes(b"not a sqlite db")

        rv = client.get("/api/login/sessions")
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["linkedin"] is False
        assert data["indeed"] is False

    @patch("routes.login._sessions_via_cdp")
    def test_cdp_fallback_when_cookie_db_unreadable(self, mock_cdp, app_client, tmp_path):
        """Use CDP cookies when the on-disk Cookies DB cannot be read."""
        client, data_dir = app_client
        mock_cdp.return_value = {"linkedin": True, "indeed": False}

        cookies_dir = data_dir / "browser_profile" / "Default" / "Network"
        cookies_dir.mkdir(parents=True)
        (cookies_dir / "Cookies").write_bytes(b"locked")

        rv = client.get("/api/login/sessions")
        assert rv.status_code == 200
        assert rv.get_json()["linkedin"] is True
        mock_cdp.assert_called_once()
