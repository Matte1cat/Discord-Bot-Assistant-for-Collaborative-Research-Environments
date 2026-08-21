import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "bot.log"


def setup_logging(log_level: str) -> None:
    LOG_DIR.mkdir(exist_ok=True)

    level = getattr(logging, log_level)

    formatter = logging.Formatter(
    (
        "%(asctime)s | %(levelname)-8s | %(name)s | "
        "service=%(service)s | check=%(check)s | %(message)s"
    ),
    defaults={
        "service": "-",
        "check": "-",
    },
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        filename=LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    logging.getLogger("discord").setLevel(logging.INFO)
    logging.getLogger("discord.http").setLevel(logging.WARNING)