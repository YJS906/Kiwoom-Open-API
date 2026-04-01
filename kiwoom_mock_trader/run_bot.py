"""Entry point for the mock trading bot."""

from __future__ import annotations

import argparse
import sys

from app.bot import TradingBot
from app.config import load_app_settings
from app.logger import setup_logger


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Kiwoom mock trading bot")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config.yaml. Copy config.yaml.example first.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single cycle and exit.",
    )
    return parser.parse_args()


def main() -> int:
    """Program entry point."""

    args = parse_args()
    settings = load_app_settings(args.config)
    logger = setup_logger(settings)
    bot = TradingBot(settings, logger)

    try:
        if args.once:
            bot.run_once()
        else:
            bot.run_forever()
    except KeyboardInterrupt:
        logger.warning("Interrupted by user.")
        return 130
    except Exception as exc:
        logger.error("Program terminated with error: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
