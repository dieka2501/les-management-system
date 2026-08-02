from __future__ import annotations

import os
import re
import shlex
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_project_env(env_path: str | os.PathLike[str] | None = None, *, override: bool = False) -> dict[str, str]:
    path = Path(env_path or PROJECT_ROOT / ".env")
    if not path.exists():
        return {}

    loaded: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        if "=" not in line:
            continue

        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not ENV_KEY_PATTERN.match(key):
            continue

        value = parse_env_value(raw_value)
        loaded[key] = value
        if override or key not in os.environ:
            os.environ[key] = value
    return loaded


def parse_env_value(raw_value: str) -> str:
    value = raw_value.strip()
    if not value:
        return ""

    try:
        parts = shlex.split(value, comments=True, posix=True)
    except ValueError:
        return value.strip("\"'")
    return " ".join(parts) if parts else ""
