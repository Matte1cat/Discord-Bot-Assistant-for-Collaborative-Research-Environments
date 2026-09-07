"""
Initializes mutable deployment configuration from versioned templates.
"""

import os
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

SERVICES_TEMPLATE = (
    PROJECT_ROOT
    / "resources"
    / "services.json"
)

RUNTIME_TEMPLATE = (
    PROJECT_ROOT
    / "resources"
    / "runtime.json"
)


def initialize_runtime_config() -> None:
    _ensure_config_file(
        environment_variable=(
            "SERVICES_CONFIG_PATH"
        ),
        template_path=SERVICES_TEMPLATE,
    )

    _ensure_config_file(
        environment_variable=(
            "RUNTIME_CONFIG_PATH"
        ),
        template_path=RUNTIME_TEMPLATE,
    )


def _ensure_config_file(
    environment_variable: str,
    template_path: Path,
) -> None:
    raw_target = os.getenv(
        environment_variable
    )

    # No custom deployment path:
    # the application will use the normal
    # versioned resource file.
    if not raw_target:
        return

    target_path = Path(
        raw_target
    )

    if target_path.exists():
        return

    if not template_path.exists():
        raise RuntimeError(
            (
                "Configuration template does "
                f"not exist: {template_path}"
            )
        )

    target_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(
        template_path,
        target_path,
    )

    print(
        (
            "Initialized runtime configuration "
            f"from template: {target_path}"
        ),
        flush=True,
    )