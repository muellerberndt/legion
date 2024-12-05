from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime
from src.util.logging import Logger
from src.services.notification_service import NotificationService

@dataclass
class JobNotification:
    """Notification about a job"""
    job_id: str
    job_type: str
    status: str
    message: str
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
    
    async def notify_completion(self, job_id: str, job_type: str, status: str, message: str,
                              started_at: Optional[datetime] = None,
                              completed_at: Optional[datetime] = None) -> None:
        """Send notification about job completion"""
        notification = JobNotification(
            job_id=job_id,
            job_type=job_type,
            status=status,
            message=message,
            started_at=started_at,
            completed_at=completed_at
        )
        
        message = self._format_notification(notification)
        
        for service in self._notification_services:
            try:
                await service.send_message(message)
            except Exception as e:
                self.logger.error(f"Failed to send job notification via {service.__class__.__name__}: {str(e)}")
    
    def _format_notification(self, notification: JobNotification) -> str:
        """Format notification message"""
        lines = [
            f"🔔 Job {notification.job_id} ({notification.job_type}) {notification.status}!",
            f"Result: {notification.message}"
        ]
        
        if notification.started_at and notification.completed_at:
            duration = notification.completed_at - notification.started_at
            lines.append(f"Duration: {duration.total_seconds():.1f}s")
            
        lines.append(f"\nGet full results:\n<code>/job {notification.job_id}</code>")
            
        return "\n".join(lines) 