"""
Provides the application entry point and starts the configured Discord bot.
"""
import logging

from bot import ThesisBot
from config import load_settings
from logging_config import setup_logging
from bootstrap import initialize_runtime_config


def main() -> None:
    settings = load_settings()

    initialize_runtime_config()

    setup_logging(settings.log_level)

    logger = logging.getLogger(__name__)
    logger.info("Starting bot")

    bot = ThesisBot(settings)

    bot.run(
        settings.bot_token,
        log_handler=None,
    )


if __name__ == "__main__":
    main()