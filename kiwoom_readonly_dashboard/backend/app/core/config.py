"""Application settings and trading config loader."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.models.trading import TradingConfig


ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Environment-backed application settings."""

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="Kiwoom Readonly Dashboard", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    api_host: str = Field(default="127.0.0.1", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    frontend_origin: str = Field(default="http://localhost:3000", alias="FRONTEND_ORIGIN")

    kiwoom_env: Literal["mock", "production"] = Field(default="mock", alias="KIWOOM_ENV")
    kiwoom_app_key: str = Field(alias="KIWOOM_APP_KEY")
    kiwoom_secret_key: str = Field(alias="KIWOOM_SECRET_KEY")
    kiwoom_account_no: str = Field(alias="KIWOOM_ACCOUNT_NO")
    kiwoom_timeout_seconds: float = Field(default=15.0, alias="KIWOOM_TIMEOUT_SECONDS")
    kiwoom_min_request_interval_seconds: float = Field(
        default=0.35,
        alias="KIWOOM_MIN_REQUEST_INTERVAL_SECONDS",
    )
    kiwoom_symbol_cache_ttl_seconds: int = Field(
        default=21600,
        alias="KIWOOM_SYMBOL_CACHE_TTL_SECONDS",
    )
    kiwoom_chart_cache_ttl_seconds: int = Field(
        default=300,
        alias="KIWOOM_CHART_CACHE_TTL_SECONDS",
    )
    kiwoom_quote_cache_ttl_seconds: int = Field(
        default=5,
        alias="KIWOOM_QUOTE_CACHE_TTL_SECONDS",
    )
    kiwoom_account_cache_ttl_seconds: int = Field(
        default=30,
        alias="KIWOOM_ACCOUNT_CACHE_TTL_SECONDS",
    )
    news_cache_ttl_seconds: int = Field(default=60, alias="NEWS_CACHE_TTL_SECONDS")

    naver_client_id: str | None = Field(default=None, alias="NAVER_CLIENT_ID")
    naver_client_secret: str | None = Field(default=None, alias="NAVER_CLIENT_SECRET")
    news_provider: Literal["auto", "naver", "rss"] = Field(default="auto", alias="NEWS_PROVIDER")

    trading_config_path_env: str | None = Field(default=None, alias="TRADING_CONFIG_PATH")
    auto_buy_enabled_env: bool | None = Field(default=None, alias="AUTO_BUY_ENABLED")
    paper_trading_env: bool | None = Field(default=None, alias="PAPER_TRADING")
    use_mock_only_env: bool | None = Field(default=None, alias="USE_MOCK_ONLY")
    real_order_enabled_env: bool | None = Field(default=None, alias="REAL_ORDER_ENABLED")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def kiwoom_rest_base_url(self) -> str:
        if self.kiwoom_env == "production":
            return "https://api.kiwoom.com"
        return "https://mockapi.kiwoom.com"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def kiwoom_ws_url(self) -> str:
        if self.kiwoom_env == "production":
            return "wss://api.kiwoom.com:10000/api/dostk/websocket"
        return "wss://mockapi.kiwoom.com:10000/api/dostk/websocket"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def runtime_dir(self) -> Path:
        return ROOT_DIR / "runtime"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def log_dir(self) -> Path:
        return ROOT_DIR / "logs"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def token_cache_file(self) -> Path:
        return self.runtime_dir / f"kiwoom_token_{self.kiwoom_env}.json"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def stock_universe_cache_file(self) -> Path:
        return self.runtime_dir / "stock_universe_cache.json"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def trading_state_file(self) -> Path:
        return self.runtime_dir / "strategy_runtime_state.json"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def trading_override_file(self) -> Path:
        return self.runtime_dir / "strategy_runtime_overrides.json"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def trading_config_path(self) -> Path:
        raw = self.trading_config_path_env or str(ROOT_DIR / "config.yaml")
        path = Path(raw)
        return path if path.is_absolute() else (ROOT_DIR / path).resolve()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origins(self) -> list[str]:
        return [self.frontend_origin, "http://127.0.0.1:3000", "http://localhost:3000"]


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge config dictionaries."""

    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML safely, returning an empty dict for missing files."""

    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_trading_config(settings: Settings) -> TradingConfig:
    """Load config.yaml and apply runtime/env overrides."""

    base = _load_yaml(settings.trading_config_path)
    runtime = {}
    if settings.trading_override_file.exists():
        runtime = json.loads(settings.trading_override_file.read_text(encoding="utf-8"))
    merged = _deep_merge(base, runtime)
    config = TradingConfig(**merged)

    if settings.auto_buy_enabled_env is not None:
        config.execution.auto_buy_enabled = settings.auto_buy_enabled_env
    if settings.paper_trading_env is not None:
        config.execution.paper_trading = settings.paper_trading_env
    if settings.use_mock_only_env is not None:
        config.execution.use_mock_only = settings.use_mock_only_env
    if settings.real_order_enabled_env is not None:
        config.execution.real_order_enabled = settings.real_order_enabled_env

    return config


def save_trading_overrides(settings: Settings, patch: dict[str, Any]) -> TradingConfig:
    """Persist runtime overrides and return the merged config."""

    current = {}
    if settings.trading_override_file.exists():
        current = json.loads(settings.trading_override_file.read_text(encoding="utf-8"))
    merged = _deep_merge(current, patch)
    settings.trading_override_file.parent.mkdir(parents=True, exist_ok=True)
    settings.trading_override_file.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return load_trading_config(settings)


@lru_cache
def get_settings() -> Settings:
    """Return cached settings."""

    settings = Settings()
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    return settings
