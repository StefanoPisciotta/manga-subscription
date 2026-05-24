from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = PROJECT_ROOT / "state"
PROFILE_DIR = STATE_DIR / "profile"
SCREENSHOTS_DIR = STATE_DIR / "screenshots"
STATE_FILE = STATE_DIR / "state.json"
LOGS_DIR = PROJECT_ROOT / "logs"

load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    telegram_chat_id: int
    dry_run: bool
    max_price_eur: float
    confirm_timeout_hours: float
    confirm_poll_seconds: int
    target_volume_override: int | None
    search_query_template: str


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variabile d'ambiente obbligatoria mancante: {name}")
    return value


def load_config() -> Config:
    target_override_raw = os.getenv("TARGET_VOLUME")
    target_override = int(target_override_raw) if target_override_raw else None

    return Config(
        telegram_bot_token=_require("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=int(_require("TELEGRAM_CHAT_ID")),
        dry_run=_bool(os.getenv("DRY_RUN"), default=True),
        max_price_eur=float(os.getenv("MAX_PRICE_EUR", "6.00")),
        confirm_timeout_hours=float(os.getenv("CONFIRM_TIMEOUT_HOURS", "6")),
        confirm_poll_seconds=int(os.getenv("CONFIRM_POLL_SECONDS", "30")),
        target_volume_override=target_override,
        search_query_template=os.getenv(
            "SEARCH_QUERY_TEMPLATE", "One Piece New Edition vol. {volume}"
        ),
    )


def ensure_dirs() -> None:
    for d in (STATE_DIR, PROFILE_DIR, SCREENSHOTS_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)
