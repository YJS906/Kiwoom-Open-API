"""Logging configuration with secret redaction."""

from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler

from app.core.config import Settings


class SecretRedactionFilter(logging.Filter):
    """Remove secrets from logs."""

    bearer_pattern = re.compile(r"Bearer\\s+[A-Za-z0-9._\\-]+")

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.secret_values = [
            settings.kiwoom_app_key,
            settings.kiwoom_secret_key,
            settings.kiwoom_account_no,
            settings.naver_client_id or "",
            settings.naver_client_secret or "",
        ]

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for secret in self.secret_values:
            if secret:
                message = message.replace(secret, "[REDACTED]")
        message = self.bearer_pattern.sub("Bearer [REDACTED]", message)
        record.msg = message
        record.args = ()
        return True


def configure_logging(settings: Settings) -> logging.Logger:
    """Configure a shared application logger."""

    logger = logging.getLogger("kiwoom_dashboard")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    filter_ = SecretRedactionFilter(settings)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.addFilter(filter_)

    logfile = RotatingFileHandler(
        settings.log_dir / "dashboard.log",
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    logfile.setFormatter(formatter)
    logfile.addFilter(filter_)

    logger.addHandler(console)
    logger.addHandler(logfile)
    return logger
