import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    bot_token: str
    test_guild_id: int | None
    log_level: str


def load_settings() -> Settings:
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is not set in the environment.")

    raw_guild_id = os.getenv("DISCORD_TEST_GUILD_ID")

    test_guild_id = None

    if raw_guild_id:
        try:
            test_guild_id = int(raw_guild_id)
        except ValueError as exc:
            raise RuntimeError(
                "DISCORD_TEST_GUILD_ID must be a valid integer."
            ) from exc

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    valid_log_levels = {
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    }

    if log_level not in valid_log_levels:
        raise RuntimeError(
            f"Invalid LOG_LEVEL: {log_level}"
        )

    return Settings(
        bot_token=bot_token,
        test_guild_id=test_guild_id,
        log_level=log_level,
    )