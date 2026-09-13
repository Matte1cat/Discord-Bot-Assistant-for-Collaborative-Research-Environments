"""Checks startup initialization with dotenv and preloaded environment values."""
import os
from pathlib import Path
from unittest.mock import Mock

import pytest
from dotenv import load_dotenv

import bootstrap
import config
import main as entrypoint


@pytest.mark.parametrize("preloaded_environment", [False, True])
def test_startup_creates_configs_and_preserves_existing_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    preloaded_environment: bool,
) -> None:
    # Work with a private environment copy, never the user's .env or configs.
    monkeypatch.setattr(os, "environ", os.environ.copy())
    for key in (
        "BOT_TOKEN", "LOG_LEVEL", "DISCORD_TEST_GUILD_ID",
        "SERVICES_CONFIG_PATH", "RUNTIME_CONFIG_PATH",
        "PYTHON_DOTENV_DISABLED",
    ):
        monkeypatch.delenv(key, raising=False)

    dotenv_directory = tmp_path / "from_dotenv"
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text(
        "BOT_TOKEN=unit-test-placeholder\n"
        "LOG_LEVEL=INFO\n"
        f"SERVICES_CONFIG_PATH={(dotenv_directory / 'services.json').as_posix()}\n"
        f"RUNTIME_CONFIG_PATH={(dotenv_directory / 'runtime.json').as_posix()}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        config, "load_dotenv",
        lambda: load_dotenv(dotenv_path=dotenv_file, override=False),
    )

    target_directory = dotenv_directory
    if preloaded_environment:
        target_directory = tmp_path / "from_environment"
        monkeypatch.setenv(
            "SERVICES_CONFIG_PATH", str(target_directory / "services.json")
        )
        monkeypatch.setenv(
            "RUNTIME_CONFIG_PATH", str(target_directory / "runtime.json")
        )

    targets = (
        target_directory / "services.json",
        target_directory / "runtime.json",
    )
    template_bytes = (
        bootstrap.SERVICES_TEMPLATE.read_bytes(),
        bootstrap.RUNTIME_TEMPLATE.read_bytes(),
    )

    # Prevent network access and changes to the application's log handlers.
    fake_bot = Mock()
    def create_bot(settings: config.Settings) -> Mock:
        assert settings.services_config_path == targets[0]
        assert settings.runtime_config_path == targets[1]
        assert all(path.is_file() for path in targets)
        return fake_bot

    monkeypatch.setattr(entrypoint, "ThesisBot", create_bot)
    monkeypatch.setattr(entrypoint, "setup_logging", Mock())

    # First startup must initialize both missing files before bot construction.
    entrypoint.main()
    assert tuple(path.read_bytes() for path in targets) == template_bytes
    fake_bot.run.assert_called_once_with("unit-test-placeholder", log_handler=None)
    if preloaded_environment:
        assert not dotenv_directory.exists()

    # A subsequent startup must not replace operational configuration.
    marker = b'{"keep_this_configuration": true}\n'
    for path in targets:
        path.write_bytes(marker)
    entrypoint.main()
    assert all(path.read_bytes() == marker for path in targets)
    assert fake_bot.run.call_count == 2
