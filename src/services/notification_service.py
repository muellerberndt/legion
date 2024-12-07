from abc import ABC, abstractmethod


class NotificationService(ABC):
    """Base class for notification services"""

    _instance = None

    @classmethod
    def get_instance(cls):
        if not cls._instance:
            cls._instance = cls()
        return cls._instance

    @abstractmethod
    async def send_message(self, message: str) -> None:
        """Send a message through the notification service"""
