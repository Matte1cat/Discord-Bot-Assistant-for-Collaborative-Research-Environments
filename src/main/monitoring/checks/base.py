from abc import ABC, abstractmethod

from monitoring.models import CheckResult


class BaseCheck(ABC):
    def __init__(self, name: str) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                "Check name must be a non-empty string."
            )

        self.name = name

    @abstractmethod
    async def run(self) -> CheckResult:
        """Execute the check and return its result."""
        pass