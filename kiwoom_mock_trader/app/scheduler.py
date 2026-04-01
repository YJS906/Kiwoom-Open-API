"""Very small synchronous scheduler."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable


class PollingScheduler:
    """Run a job repeatedly every N seconds."""

    def __init__(self, interval_seconds: int, logger: logging.Logger) -> None:
        self.interval_seconds = interval_seconds
        self.logger = logger.getChild("scheduler")

    def run(self, job: Callable[[], None]) -> None:
        """Run a job forever until interrupted or it raises."""

        while True:
            started = time.monotonic()
            job()
            elapsed = time.monotonic() - started
            sleep_for = max(self.interval_seconds - elapsed, 0)
            if sleep_for:
                time.sleep(sleep_for)
