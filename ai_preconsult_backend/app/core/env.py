"""Load .env file once on import. Place .env in the project root (ai_preconsult_backend/)."""

import os
from pathlib import Path


_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"

if _ENV_PATH.exists():
    with _ENV_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value and key not in os.environ:
                os.environ[key] = value


def require_env(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"Missing required env var: {key} (check .env file)")
    return val
