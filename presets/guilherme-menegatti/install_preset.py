#!/usr/bin/env python3
"""Install Guilherme Menegatti preset into ~/.autoapply/."""

from __future__ import annotations

import sys
from pathlib import Path

PRESET_DIR = Path(__file__).resolve().parent


def main() -> int:
    from presets.bootstrap import _load_api_key, install_preset

    api_key = _load_api_key(PRESET_DIR)
    if not api_key:
        secrets_file = PRESET_DIR / "secrets.env"
        raise SystemExit(
            "Missing Groq API key. Create secrets.env with GROQ_API_KEY=... "
            f"or set GROQ_API_KEY before running.\nExpected: {secrets_file}"
        )

    try:
        installed = install_preset(PRESET_DIR, force=True)
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Preset install failed: {exc}", file=sys.stderr)
        return 1

    if installed:
        print("Preset installed successfully.")
        print(f"  Data dir: {Path.home() / '.autoapply'}")
    else:
        print("Preset already installed (use --force via bootstrap if needed).")
    print("")
    print("Next steps for Guilherme:")
    print("  1) Open JobApply Assistant")
    print("  2) Settings -> Platform Login -> LinkedIn (one-time login in app browser)")
    print("  3) Settings -> Import Jobs from Home Server (your home PC URL + token)")
    print("  4) Applications -> review imported jobs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
