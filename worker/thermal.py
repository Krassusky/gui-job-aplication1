"""Host thermal guards for the Ubuntu Job Hunter (lm-sensors).

Mirrors thresholds used by Immich migrator on the same iMac:
  HOT:  CPU >= 76C or SMC >= 80C or fan >= 2550 RPM
  COOL: CPU <= 64C and SMC <= 72C and fan < 2200 RPM
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


HOT_CPU_TEMP = _env_int("HUNTER_HOT_CPU_TEMP", 76)
HOT_SMC_TEMP = _env_int("HUNTER_HOT_SMC_TEMP", 80)
HOT_FAN_RPM = _env_int("HUNTER_HOT_FAN_RPM", 2550)
COOL_CPU_TEMP = _env_int("HUNTER_COOL_CPU_TEMP", 64)
COOL_SMC_TEMP = _env_int("HUNTER_COOL_SMC_TEMP", 72)
COOL_FAN_RPM = _env_int("HUNTER_COOL_FAN_RPM", 2200)
COOLDOWN_POLL_SEC = _env_int("HUNTER_COOLDOWN_POLL_SEC", 45)


@dataclass
class SensorSnapshot:
    cpu_c: int | None = None
    smc_c: int | None = None
    fan_rpm: int | None = None

    def as_dict(self) -> dict:
        return {"cpu_c": self.cpu_c, "smc_c": self.smc_c, "fan_rpm": self.fan_rpm}

    def summary(self) -> str:
        return (
            f"cpu={self.cpu_c if self.cpu_c is not None else '?'}C "
            f"smc={self.smc_c if self.smc_c is not None else '?'}C "
            f"fan={self.fan_rpm if self.fan_rpm is not None else '?'}RPM"
        )


def read_sensors() -> SensorSnapshot:
    """Parse `sensors` output (coretemp + applesmc) like the Ubuntu dashboard."""
    try:
        output = subprocess.check_output(
            ["sensors"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError) as e:
        logger.debug("lm-sensors unavailable: %s", e)
        return SensorSnapshot()

    cpu = smc = fan = None
    for line in output.splitlines():
        if "Package id 0:" in line:
            m = re.search(r"\+(\d+)", line)
            if m:
                cpu = int(m.group(1))
        elif "TC0p:" in line:
            m = re.search(r"\+(\d+)", line)
            if m:
                smc = int(m.group(1))
        elif line.startswith("Main :"):
            parts = line.split()
            if len(parts) >= 3 and parts[2].isdigit():
                fan = int(parts[2])
    return SensorSnapshot(cpu_c=cpu, smc_c=smc, fan_rpm=fan)


def is_too_hot(snap: SensorSnapshot | None = None) -> bool:
    s = snap or read_sensors()
    if s.cpu_c is not None and s.cpu_c >= HOT_CPU_TEMP:
        return True
    if s.smc_c is not None and s.smc_c >= HOT_SMC_TEMP:
        return True
    if s.fan_rpm is not None and s.fan_rpm >= HOT_FAN_RPM:
        return True
    return False


def is_cool_enough(snap: SensorSnapshot | None = None) -> bool:
    s = snap or read_sensors()
    if s.cpu_c is not None and s.cpu_c > COOL_CPU_TEMP:
        return False
    if s.smc_c is not None and s.smc_c > COOL_SMC_TEMP:
        return False
    if s.fan_rpm is not None and s.fan_rpm >= COOL_FAN_RPM:
        return False
    # If no sensors available, treat as cool enough (do not block hunting).
    if s.cpu_c is None and s.smc_c is None and s.fan_rpm is None:
        return True
    return True
