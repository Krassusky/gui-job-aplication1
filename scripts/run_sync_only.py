"""Run sync API only (no Job Hunter search cycles)."""

from __future__ import annotations

import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from worker.sync_server import run_sync_server

if __name__ == "__main__":
    run_sync_server()
