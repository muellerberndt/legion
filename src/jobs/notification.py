from dataclasses import dataclass
from typing import Optional, Dict, List
from datetime import datetime
from src.util.logging import Logger
from src.services.db_notification_service import DatabaseNotificationService
from src.services.notification_service import NotificationService


@dataclass
class JobNotification:
    """Notification about a job"""

    job_id: str
    job_type: str
    status: str
    message: Optional[str] = None
    error: Optional[str] = None
    outputs: Optional[list] = None
    data: Optional[Dict] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class JobNotifier:
    """Handles job notifications"""

    _instance = None
    _notification_services: List[NotificationService] = []

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(JobNotifier, cls).__new__(cls)
            cls._instance.initialize()
        return cls._instance

    def initialize(self):
        """Initialize the notifier"""
        self.logger = Logger("JobNotifier")

    @classmethod
    def register_service(cls, service: NotificationService):
        """Register a notification service"""
        if service not in cls._notification_services:
            cls._notification_services.append(service)

    async def notify_completion(
        self,
        job_id: str,
        job_type: str,
        status: str,
        message: Optional[str] = None,
        outputs: Optional[list] = None,
        data: Optional[Dict] = None,
        error: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> None:
        """Send notification about job completion"""
        try:
            notification = JobNotification(
                job_id=job_id,
                job_type=job_type,
                status=status,
                message=message,
                error=error,
                outputs=outputs,
                data=data,
                started_at=started_at,
                completed_at=completed_at,
            )

            message = self._format_notification(notification)

            # Send via all registered services
            for service in self._notification_services:
                try:
                    await service.send_message(message)
                except Exception as e:
                    self.logger.error(f"Failed to send job notification via {service.__class__.__name__}: {str(e)}")

        except Exception as e:
            self.logger.error(f"Failed to send job notification: {e}")
            raise

    def _format_notification(self, notification: JobNotification) -> str:
        """Format notification message"""
        lines = [f"🔔 Job {notification.job_id} ({notification.job_type}) {notification.status}!"]

        # Add result or error
        if notification.error:
            lines.append(f"Error: {notification.error}")
        elif notification.message:
            lines.append(f"Result: {notification.message}")

        # Add duration if available
        if notification.started_at and notification.completed_at:
            duration = notification.completed_at - notification.started_at
            lines.append(f"Duration: {duration.total_seconds():.1f}s")

        # Add link to get full results
        lines.extend(["", "Get full results:", f"/job {notification.job_id}"])

        return "\n".join(lines)
