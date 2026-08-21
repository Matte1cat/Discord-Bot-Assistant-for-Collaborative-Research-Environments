from dataclasses import dataclass

from monitoring.checks.base import BaseCheck


@dataclass(frozen=True)
class Service:
    key: str
    display_name: str
    checks: tuple[BaseCheck, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key.strip():
            raise ValueError(
                "Service key must be a non-empty string."
            )

        if (
            not isinstance(self.display_name, str)
            or not self.display_name.strip()
        ):
            raise ValueError(
                "Service display name must be a non-empty string."
            )

        if not self.checks:
            raise ValueError(
                f"Service '{self.key}' must have at least one check."
            )