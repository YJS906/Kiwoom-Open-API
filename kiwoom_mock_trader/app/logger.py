"""Logging setup with basic redaction."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from app.models import AppSettings
from app.utils import ensure_directory, resolve_path

try:
    from rich.logging import RichHandler
except ImportError:  # pragma: no cover - fallback when dependencies are absent.
    RichHandler = None


class SensitiveDataFilter(logging.Filter):
    """Redact known secrets and bearer tokens from log messages."""

    bearer_pattern = re.compile(r"Bearer\\s+[A-Za-z0-9._\\-]+")

    def __init__(self, settings: AppSettings) -> None:
        super().__init__()
        self._secret_values = [
            settings.credentials.app_key,
            settings.credentials.secret_key,
            settings.credentials.account_no,
            settings.credentials.account_password or "",
        ]

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for secret in self._secret_values:
            if secret:
                message = message.replace(secret, "[REDACTED]")
        message = self.bearer_pattern.sub("Bearer [REDACTED]", message)
        record.msg = message
        record.args = ()
        return True


def setup_logger(settings: AppSettings) -> logging.Logger:
    """Configure console and file logging."""

    logger = logging.getLogger("kiwoom_mock_trader")
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, settings.logging.level.upper(), logging.INFO))
    logger.propagate = False

    filter_ = SensitiveDataFilter(settings)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    log_dir = ensure_directory(resolve_path(settings.project_root, settings.logging.directory))
    log_file = Path(log_dir) / settings.logging.file_name

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.addFilter(filter_)
    logger.addHandler(file_handler)

    if RichHandler is not None:
        console_handler: logging.Handler = RichHandler(
            rich_tracebacks=True,
            markup=False,
            show_path=False,
        )
    else:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

    console_handler.addFilter(filter_)
    logger.addHandler(console_handler)
    return logger

