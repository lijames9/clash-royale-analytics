"""Project paths and settings, read from the .env file at the project root."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
STATE_DIR = DATA_DIR / "state"

load_dotenv(PROJECT_ROOT / ".env")

API_BASE = os.getenv("CR_API_BASE", "https://api.clashroyale.com/v1").rstrip("/")


def api_token() -> str:
    token = os.getenv("CR_API_TOKEN", "").strip()
    if not token or token == "paste-your-token-here":
        raise RuntimeError(
            "No API token found. Copy .env.example to .env and paste your key "
            "from https://developer.clashroyale.com into CR_API_TOKEN."
        )
    return token


def seed_tags() -> list[str]:
    raw = os.getenv("CR_SEED_TAGS", "")
    return [t.strip() for t in raw.replace(";", ",").split(",") if t.strip()]


for _d in (RAW_DIR, PROCESSED_DIR, STATE_DIR):
    _d.mkdir(parents=True, exist_ok=True)
