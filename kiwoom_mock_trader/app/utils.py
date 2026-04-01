"""Shared helpers."""

from __future__ import annotations

import json
import re
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml


def ensure_directory(path: Path) -> Path:
    """Create a directory if it does not exist."""

    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_path(project_root: Path, value: str | Path) -> Path:
    """Resolve relative paths under the project root."""

    path = Path(value)
    return path if path.is_absolute() else (project_root / path).resolve()


def load_yaml_file(path: Path) -> dict[str, Any]:
    """Load YAML config safely."""

    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    return data


def load_json_file(path: Path, default: Any = None) -> Any:
    """Read a JSON file if it exists."""

    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json_file(path: Path, payload: Any) -> None:
    """Persist JSON data using UTF-8."""

    ensure_directory(path.parent)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)


def now_in_timezone(timezone_name: str) -> datetime:
    """Return timezone-aware current time."""

    return datetime.now(get_timezone(timezone_name))


def today_yyyymmdd(timezone_name: str) -> str:
    """Return today's date in YYYYMMDD."""

    return now_in_timezone(timezone_name).strftime("%Y%m%d")


def get_timezone(timezone_name: str):
    """Return an IANA timezone, falling back safely on Windows without tzdata."""

    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        if timezone_name == "Asia/Seoul":
            return timezone(timedelta(hours=9), name="Asia/Seoul")
        return timezone.utc


def parse_hhmm(value: str) -> time:
    """Parse HH:MM strings from config."""

    return time.fromisoformat(value)


def is_within_time_window(now: datetime, start_hhmm: str, end_hhmm: str) -> bool:
    """Check whether local time is inside the allowed trading window."""

    start_time = parse_hhmm(start_hhmm)
    end_time = parse_hhmm(end_hhmm)
    now_time = now.timetz().replace(tzinfo=None)
    return start_time <= now_time <= end_time


def safe_int(value: Any) -> int:
    """Convert Kiwoom string numbers into int."""

    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)

    text = str(value).strip().replace(",", "")
    if not text:
        return 0

    text = text.replace("+", "")
    if text in {"-", "."}:
        return 0
    return int(float(text))


def safe_abs_int(value: Any) -> int:
    """Parse numbers and force non-negative price style values."""

    return abs(safe_int(value))


def safe_float(value: Any) -> float:
    """Convert Kiwoom string numbers into float."""

    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().replace(",", "")
    if not text:
        return 0.0
    text = text.replace("+", "")
    return float(text)


def normalize_symbol(symbol: str) -> str:
    """Normalize a stock symbol to its plain numeric code."""

    text = re.sub(r"[^0-9A-Za-z_:]", "", symbol).upper()
    text = re.sub(r"^[A-Z]+:", "", text)
    match = re.match(r"^A?(\d{6})(?:_[A-Z]+)?$", text)
    if match:
        return match.group(1)
    return text


def format_quote_symbol(exchange: str, symbol: str) -> str:
    """Format quote/chart symbols following Kiwoom's documented pattern."""

    return f"{exchange}:{normalize_symbol(symbol)}"


def is_mock_url(url: str) -> bool:
    """Return True only for Kiwoom mock endpoints."""

    hostname = urlparse(url).hostname or ""
    return hostname.lower() == "mockapi.kiwoom.com"


def redact_value(value: str | None, keep: int = 4) -> str:
    """Hide sensitive values in logs."""

    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return f"{value[:keep]}{'*' * max(4, len(value) - keep)}"
