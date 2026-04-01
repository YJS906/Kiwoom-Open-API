"""Load .env and YAML configuration."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from app.exceptions import KiwoomConfigurationError
from app.models import AppSettings, Credentials
from app.utils import ensure_directory, load_yaml_file, resolve_path


def load_app_settings(config_path: str | Path) -> AppSettings:
    """Load config.yaml and .env into one validated settings object."""

    path = Path(config_path).resolve()
    if not path.exists():
        raise KiwoomConfigurationError(
            f"Config file does not exist: {path}. Copy config.yaml.example to config.yaml first."
        )

    project_root = path.parent
    dotenv_path = project_root / ".env"
    load_dotenv(dotenv_path=dotenv_path, override=False)

    missing = [
        key
        for key in ("KIWOOM_APP_KEY", "KIWOOM_SECRET_KEY", "KIWOOM_ACCOUNT_NO")
        if not os.getenv(key)
    ]
    if missing:
        raise KiwoomConfigurationError(
            "Missing required environment variables in .env: " + ", ".join(missing)
        )

    data = load_yaml_file(path)
    merged_data = dict(data)
    merged_data["environment"] = os.getenv("KIWOOM_ENV", data.get("environment", "mock"))

    settings = AppSettings(
        **merged_data,
        credentials=Credentials(
            app_key=os.environ["KIWOOM_APP_KEY"],
            secret_key=os.environ["KIWOOM_SECRET_KEY"],
            account_no=os.environ["KIWOOM_ACCOUNT_NO"],
            account_password=os.getenv("KIWOOM_ACCOUNT_PASSWORD"),
        ),
        project_root=project_root,
    )
    _prepare_runtime_directories(settings)
    _validate_mock_only(settings)
    return settings


def _prepare_runtime_directories(settings: AppSettings) -> None:
    """Create directories used by logs and state persistence."""

    ensure_directory(resolve_path(settings.project_root, settings.runtime.state_dir))
    ensure_directory(resolve_path(settings.project_root, settings.runtime.orders_dir))
    ensure_directory(resolve_path(settings.project_root, settings.logging.directory))


def _validate_mock_only(settings: AppSettings) -> None:
    """Fail fast if someone tries to use this project outside mock mode."""

    if settings.environment.lower() != "mock":
        raise KiwoomConfigurationError(
            "This sample project is intentionally restricted to the mock environment only."
        )

    if not settings.safety.use_mock_only:
        raise KiwoomConfigurationError(
            "safety.use_mock_only must remain true in this project."
        )
