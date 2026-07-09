"""Allow ``python -m worker.job_hunter``."""

from worker.job_hunter import main

if __name__ == "__main__":
    raise SystemExit(main())
