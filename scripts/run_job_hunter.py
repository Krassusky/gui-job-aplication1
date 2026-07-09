#!/usr/bin/env python3
"""Entry point for the Job Hunter worker on Ubuntu/home server."""

from worker.job_hunter import main

if __name__ == "__main__":
    raise SystemExit(main())
