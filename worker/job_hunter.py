"""Job Hunter worker — headless search, score, filter, and save discoveries.

Runs on Ubuntu/home server 24/7. Does not apply to jobs or block on review.
Optionally serves a sync API for Mac clients to import discoveries.
Supports dashboard start/stop and thermal pause (lm-sensors).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

from bot.bot import SEARCHERS, _save_job_description
from bot.browser import BrowserManager
from config.settings import AppConfig, get_data_dir, load_config
from core.filter import score_job
from db.database import Database
from worker.hunter_state import hunter_state
from worker.linkedin_session import ensure_linkedin_session
from worker.sync_server import start_sync_server_thread
from worker.thermal import (
    COOLDOWN_POLL_SEC,
    is_cool_enough,
    is_too_hot,
    read_sensors,
)

logger = logging.getLogger(__name__)


def _load_dotenv() -> None:
    """Load repo `.env` into os.environ if present (does not override existing)."""
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("'").strip('"')
                if key and key not in os.environ:
                    os.environ[key] = value
            logger.info("Loaded environment from %s", path)
            return
        except OSError as e:
            logger.warning("Could not read %s: %s", path, e)


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _load_worker_config(config_path: str | None = None) -> AppConfig:
    if config_path:
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config not found: {path}")
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
        return AppConfig(**data)

    config = load_config()
    if config is None:
        raise RuntimeError(
            "No configuration found. Run setup or pass --config PATH."
        )
    return config


def _interruptible_sleep(seconds: int, *, honor_stop: bool = True) -> None:
    for _ in range(max(0, seconds)):
        if honor_stop and hunter_state.cycle_should_stop():
            return
        time.sleep(1)


def _wait_for_cooldown(*, require_want_running: bool = True) -> bool:
    """Pause while hot. Returns False if stop requested during wait."""
    snap = read_sensors()
    hunter_state.update_sensors(snap.as_dict())
    if not is_too_hot(snap):
        return True

    reason = f"system hot ({snap.summary()})"
    logger.warning("PAUSED: %s — waiting to cool", reason)
    hunter_state.set_run_state("paused_thermal", reason, snap.as_dict())
    hunter_state.record("thermal", message=f"PAUSED: {reason}")

    while True:
        if require_want_running and not hunter_state.want_running():
            return False
        snap = read_sensors()
        hunter_state.update_sensors(snap.as_dict())
        if is_cool_enough(snap):
            logger.info("RESUMED: temps normal (%s)", snap.summary())
            if hunter_state.want_running():
                hunter_state.set_run_state("running", "", snap.as_dict())
            hunter_state.record("thermal", message=f"RESUMED: {snap.summary()}")
            return True
        logger.info(
            "  still hot (%s) — recheck in %ss",
            snap.summary(),
            COOLDOWN_POLL_SEC,
        )
        _interruptible_sleep(COOLDOWN_POLL_SEC, honor_stop=require_want_running)
        if require_want_running and hunter_state.cycle_should_stop():
            return False



def run_hunt_cycle(
    config: AppConfig,
    db: Database,
    stop_flag: list[bool] | None = None,
) -> int:
    """Run one search cycle. Returns number of jobs saved."""
    def _stopped() -> bool:
        if stop_flag is not None:
            return bool(stop_flag[0])
        return hunter_state.cycle_should_stop()

    saved = 0
    profile_dir = get_data_dir() / "profile"
    browser = None

    try:
        browser = BrowserManager(config)
        page = browser.get_page()

        if "linkedin" in (config.bot.enabled_platforms or []):
            if not ensure_linkedin_session(page):
                hunter_state.record(
                    "error",
                    message="LinkedIn session unavailable — check LINKEDIN_EMAIL/PASSWORD or browser_profile",
                )
                return 0

        enabled_searchers = [
            SEARCHERS[p]()
            for p in config.bot.enabled_platforms
            if p in SEARCHERS
        ]
        if not enabled_searchers:
            logger.warning("No enabled search platforms configured")
            return 0

        criteria = config.search_criteria
        if not criteria.job_titles or not criteria.locations:
            logger.warning(
                "Job search not configured: add job titles and locations in config"
            )
            return 0

        for searcher in enabled_searchers:
            if _stopped():
                break
            try:
                for raw_job in searcher.search(config.search_criteria, page=page):
                    if _stopped():
                        break

                    logger.info(
                        "Found: %s at %s (%s)",
                        raw_job.title,
                        raw_job.company,
                        raw_job.platform,
                    )
                    hunter_state.record(
                        "found",
                        job_title=raw_job.title,
                        company=raw_job.company,
                        platform=raw_job.platform,
                    )

                    scored = score_job(raw_job, config, db)
                    if not scored.pass_filter:
                        logger.debug(
                            "Filtered: %s — %s",
                            raw_job.title,
                            scored.skip_reason,
                        )
                        hunter_state.record(
                            "filtered",
                            job_title=raw_job.title,
                            company=raw_job.company,
                            platform=raw_job.platform,
                            score=scored.score,
                            reason=scored.skip_reason or "",
                        )
                        continue

                    desc_path = _save_job_description(scored, profile_dir)
                    app_id = db.save_discovered_job(
                        external_id=raw_job.external_id,
                        platform=raw_job.platform,
                        job_title=raw_job.title,
                        company=raw_job.company,
                        location=raw_job.location,
                        salary=raw_job.salary,
                        apply_url=raw_job.apply_url,
                        match_score=scored.score,
                        description_path=str(desc_path) if desc_path else None,
                        description_text=raw_job.description,
                        status="pending_sync",
                    )
                    if app_id:
                        saved += 1
                        logger.info(
                            "Saved job id=%s score=%s: %s at %s",
                            app_id,
                            scored.score,
                            raw_job.title,
                            raw_job.company,
                        )
                        hunter_state.record(
                            "saved",
                            job_title=raw_job.title,
                            company=raw_job.company,
                            platform=raw_job.platform,
                            score=scored.score,
                            job_id=app_id,
                        )
            except Exception as e:
                logger.error("Search cycle error on %s: %s", searcher, e)
                hunter_state.record("error", message=str(e))

    finally:
        if browser:
            browser.close()

    return saved


def hunt_loop(config_loader, db: Database) -> None:
    """Run hunt cycles until stop is requested. Used by dashboard Start."""
    logger.info("Hunt loop started")
    hunter_state.set_run_state("running")
    while hunter_state.want_running():
        if not _wait_for_cooldown():
            break
        try:
            config = config_loader()
        except Exception as e:
            logger.error("Failed to load config: %s", e)
            hunter_state.record("error", message=f"config: {e}")
            break

        snap = read_sensors()
        hunter_state.update_sensors(snap.as_dict())
        if is_too_hot(snap):
            continue

        saved = run_hunt_cycle(config, db)
        logger.info("Hunt cycle complete — saved %d job(s)", saved)
        hunter_state.record("cycle", message=str(saved))

        if not hunter_state.want_running():
            break
        _interruptible_sleep(config.bot.search_interval_seconds)

    hunter_state.set_run_state("stopped", "stopped")
    logger.info("Hunt loop stopped")


def run_job_hunter(
    config: AppConfig,
    db: Database | None = None,
    *,
    enable_sync: bool = True,
    once: bool = False,
    auto_start: bool = True,
) -> None:
    """Main Job Hunter process: sync API + optional auto-start hunt loop."""
    database = db or Database(get_data_dir() / "autoapply.db")

    if once:
        loader = lambda: config  # noqa: E731
    else:
        loader = _load_worker_config

    hunter_state.configure(config_loader=loader, db=database)

    if enable_sync and os.environ.get("AUTOAPPLY_SYNC_DISABLED", "").lower() not in (
        "1",
        "true",
        "yes",
    ):
        start_sync_server_thread(db=database)
        logger.info("Sync API enabled")

    logger.info(
        "Job Hunter process ready — interval=%ss platforms=%s auto_start=%s",
        config.bot.search_interval_seconds,
        config.bot.enabled_platforms,
        auto_start,
    )

    if once:
        if not _wait_for_cooldown(require_want_running=False):
            return
        # Explicit stop_flag so cycle is not blocked by want_running=False
        saved = run_hunt_cycle(config, database, stop_flag=[False])
        logger.info("Hunt cycle complete — saved %d job(s)", saved)
        hunter_state.record("cycle", message=str(saved))
        return

    if auto_start:
        hunter_state.request_start()

    # Keep process alive while sync server (and optional hunt thread) run.
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        hunter_state.request_stop()
        logger.info("Job Hunter stopped")


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    parser = argparse.ArgumentParser(description="AutoApply Job Hunter worker")
    parser.add_argument(
        "--config",
        help="Path to config.json (default: ~/.autoapply/config.json)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single hunt cycle and exit",
    )
    parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Do not start the sync API server",
    )
    parser.add_argument(
        "--stopped",
        action="store_true",
        help="Start sync/dashboard only; do not begin hunting until Start is clicked",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    _setup_logging(verbose=args.verbose)

    try:
        config = _load_worker_config(args.config)
    except Exception as e:
        logger.error("Failed to load config: %s", e)
        return 1

    try:
        run_job_hunter(
            config,
            enable_sync=not args.no_sync,
            once=args.once,
            auto_start=not args.stopped and not args.once,
        )
    except KeyboardInterrupt:
        logger.info("Job Hunter stopped")
        return 0
    except Exception:
        logger.exception("Job Hunter crashed")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
