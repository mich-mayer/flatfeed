from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional, Tuple

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = ".env"


def _load_env_file() -> None:
    env_file = os.getenv("ENV_FILE", DEFAULT_ENV_FILE).strip() or DEFAULT_ENV_FILE
    env_path = Path(env_file)
    if not env_path.is_absolute():
        env_path = PROJECT_ROOT / env_path
    load_dotenv(env_path)


def _as_int(value: Optional[str], default: int) -> int:
    if value is None or value == "":
        return default
    return int(value)


def _as_float(value: Optional[str], default: float) -> float:
    if value is None or value == "":
        return default
    return float(value)


def _as_bool(value: Optional[str], default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_csv(value: Optional[str]) -> Tuple[str, ...]:
    if not value:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _as_int_csv(value: Optional[str]) -> Tuple[int, ...]:
    if not value:
        return ()
    return tuple(int(item.strip()) for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    database_url: str
    openai_api_key: Optional[str]
    openai_input_price_per_1m: float
    openai_output_price_per_1m: float
    telegram_bot_token: Optional[str]
    dashboard_url: Optional[str]
    dashboard_port: int
    dashboard_autostart: bool
    bot_scan_interval_seconds: int
    bot_scan_min_seconds: int
    bot_scan_max_seconds: int
    bot_background_enabled: bool
    bot_notification_limit_per_user: int
    manual_refresh_timeout_seconds: int
    admin_telegram_user_ids: Tuple[int, ...]
    source_failure_alert_threshold: int
    source_alert_cooldown_seconds: int
    synthetic_seed: int
    synthetic_listing_count: int
    ai_qa_enabled: bool
    ai_qa_provider: str
    ai_qa_model: str
    ai_qa_alert_risk_threshold: int
    ai_qa_daily_max_cost_usd: float
    ai_qa_max_listing_chars: int
    ai_qa_backfill_batch_size: int
    ai_qa_concurrency: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _load_env_file()
    bot_scan_interval_seconds = _as_int(os.getenv("BOT_SCAN_INTERVAL_SECONDS"), 3600)
    bot_scan_min_seconds = _as_int(
        os.getenv("BOT_SCAN_MIN_SECONDS"),
        bot_scan_interval_seconds,
    )
    bot_scan_max_seconds = _as_int(
        os.getenv("BOT_SCAN_MAX_SECONDS"),
        bot_scan_interval_seconds,
    )
    if bot_scan_max_seconds < bot_scan_min_seconds:
        bot_scan_max_seconds = bot_scan_min_seconds

    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./data/flatfeed.db"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_input_price_per_1m=_as_float(
            os.getenv("OPENAI_INPUT_PRICE_PER_1M"),
            0.75,
        ),
        openai_output_price_per_1m=_as_float(
            os.getenv("OPENAI_OUTPUT_PRICE_PER_1M"),
            4.50,
        ),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        dashboard_url=(os.getenv("DASHBOARD_URL") or "").strip() or None,
        dashboard_port=_as_int(os.getenv("DASHBOARD_PORT"), 8502),
        dashboard_autostart=_as_bool(os.getenv("DASHBOARD_AUTOSTART"), True),
        bot_scan_interval_seconds=bot_scan_interval_seconds,
        bot_scan_min_seconds=bot_scan_min_seconds,
        bot_scan_max_seconds=bot_scan_max_seconds,
        bot_background_enabled=_as_bool(os.getenv("BOT_BACKGROUND_ENABLED"), False),
        bot_notification_limit_per_user=_as_int(
            os.getenv("BOT_NOTIFICATION_LIMIT_PER_USER"),
            10,
        ),
        manual_refresh_timeout_seconds=_as_int(
            os.getenv("MANUAL_REFRESH_TIMEOUT_SECONDS"),
            120,
        ),
        admin_telegram_user_ids=_as_int_csv(os.getenv("ADMIN_TELEGRAM_USER_IDS")),
        source_failure_alert_threshold=_as_int(
            os.getenv("SOURCE_FAILURE_ALERT_THRESHOLD"),
            3,
        ),
        source_alert_cooldown_seconds=_as_int(
            os.getenv("SOURCE_ALERT_COOLDOWN_SECONDS"),
            3600,
        ),
        synthetic_seed=_as_int(os.getenv("SYNTHETIC_SEED"), 20260623),
        synthetic_listing_count=max(1, _as_int(os.getenv("SYNTHETIC_LISTING_COUNT"), 15)),
        ai_qa_enabled=_as_bool(os.getenv("AI_QA_ENABLED"), False),
        ai_qa_provider=os.getenv("AI_QA_PROVIDER", "mock").strip().lower(),
        ai_qa_model=os.getenv("AI_QA_MODEL", "gpt-5.4-mini"),
        ai_qa_alert_risk_threshold=_as_int(
            os.getenv("AI_QA_ALERT_RISK_THRESHOLD"),
            75,
        ),
        ai_qa_daily_max_cost_usd=_as_float(
            os.getenv("AI_QA_DAILY_MAX_COST_USD"),
            0.25,
        ),
        ai_qa_max_listing_chars=_as_int(os.getenv("AI_QA_MAX_LISTING_CHARS"), 6000),
        ai_qa_backfill_batch_size=_as_int(os.getenv("AI_QA_BACKFILL_BATCH_SIZE"), 10),
        ai_qa_concurrency=max(1, _as_int(os.getenv("AI_QA_CONCURRENCY"), 3)),
    )
