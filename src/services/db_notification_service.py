from src.services.notification_service import NotificationService
from src.models.base import Notification
from src.backend.database import DBSessionMixin
from src.util.logging import Logger


class DatabaseNotificationService(NotificationService, DBSessionMixin):
    """Service for writing notifications to the database"""

    def __init__(self):
        super().__init__()
        self.logger = Logger("DatabaseNotificationService")

    async def send_message(self, message: str) -> None:
        """Send a message by writing it to the notifications table"""
        try:
            if not message or not message.strip():
                self.logger.debug("Skipping empty message")
                return

            async with self.get_async_session() as session:
                notification = Notification(message=message)
                session.add(notification)
                await session.commit()
            self.logger.info(f"Notification saved to database: {message[:50]}...")

        except Exception as e:
            self.logger.error(f"Failed to save notification to database: {e}")
            raise
