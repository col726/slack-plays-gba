from abc import ABC, abstractmethod


class BaseBotAdapter(ABC):
    @abstractmethod
    def start(self) -> None:
        """Start the bot. Blocks until stopped."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Signal the bot to stop."""
        ...

    def post_screenshot(self, caption: str = "") -> None:
        """Post a screenshot to the platform. No-op for platforms that don't support it."""
        pass
