"""Job Hunter worker — headless search, score, filter, and save discoveries.

Runs on Ubuntu/home server 24/7. Does not apply to jobs or block on review.
Optionally serves a sync API for Mac clients to import discoveries.
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
from worker.sync_server import start_sync_server_thread

logger = logging.getLogger(__name__)


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _load_worker_config(config_path: str | None) -> AppConfig:
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


def _interruptible_sleep(stop_flag: list[bool], seconds: int) -> None:
    for _ in range(seconds):
        if stop_flag[0]:
            return
        time.sleep(1)


def run_hunt_cycle(
    config: AppConfig,
    db: Database,
    stop_flag: list[bool] | None = None,
) -> int:
    """Run one search cycle. Returns number of jobs saved."""
    stop = stop_flag if stop_flag is not None else [False]
    saved = 0
    profile_dir = get_data_dir() / "profile"
    browser = None

    try:
        browser = BrowserManager(config)
        page = browser.get_page()

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
            if stop[0]:
                break
            try:
                for raw_job in searcher.search(config.search_criteria, page=page):
                    if stop[0]:
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


def run_job_hunter(
    config: AppConfig,
    db: Database | None = None,
    *,
    enable_sync: bool = True,
    once: bool = False,
) -> None:
    """Main Job Hunter loop."""
    database = db or Database(get_data_dir() / "autoapply.db")
    stop_flag = [False]

    if enable_sync and os.environ.get("AUTOAPPLY_SYNC_DISABLED", "").lower() not in (
        "1",
        "true",
        "yes",
    ):
        start_sync_server_thread(db=database)
        logger.info("Sync API enabled")

    logger.info(
        "Job Hunter started — interval=%ss platforms=%s",
        config.bot.search_interval_seconds,
        config.bot.enabled_platforms,
    )

    while not stop_flag[0]:
        saved = run_hunt_cycle(config, database, stop_flag)
        logger.info("Hunt cycle complete — saved %d job(s)", saved)
        hunter_state.record("cycle", message=str(saved))

        if once:
            break

        _interruptible_sleep(stop_flag, config.bot.search_interval_seconds)


def main(argv: list[str] | None = None) -> int:
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
