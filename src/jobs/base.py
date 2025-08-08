from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid
from src.util.logging import Logger
from src.models.job import JobRecord
from src.backend.database import DBSessionMixin
from abc import ABC, abstractmethod
from src.services.db_notification_service import DatabaseNotificationService
from src.util.formatting import ActionResultFormatter
from src.actions.result import ActionResult


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobResult(DBSessionMixin):
    """Result of a job execution"""

    # Maximum length for Telegram messages
    MAX_MESSAGE_LENGTH = 4096

    def __init__(self, success: bool, message: str = None, data: Dict = None, outputs: List[str] = None):
        """Initialize a job result

        Args:
            success: Whether the job completed successfully
            message: Optional status/result message
            data: Optional dictionary of result data
            outputs: Optional list of output strings
        """
        DBSessionMixin.__init__(self)
        self.success = success
        self.message = message
        self.data = data or {}
        self.outputs = outputs or []
        self.logger = Logger("JobResult")

    def add_output(self, line: str) -> None:
        """Add a line to the output"""
        if self.outputs is None:
            self.outputs = []
        self.outputs.append(line)

    def get_output(self) -> str:
        """Get the complete output as a string"""
        if not self.outputs:
            if self.message:
                return self.message
            return "No output available"

        return "\n".join(self.outputs)

    def generate_html(self) -> str:
        """Generate HTML report of detailed results"""
        if not self.data.get("action_results"):
            return None

        html = ["<html><body>"]
        html.append("<h1>Detailed Action Results</h1>")

        for action in self.data["action_results"]:
            html.append(f"<h2>Command: /{action['command']}</h2>")
            html.append(f"<p>Executed at: {action['timestamp']}</p>")

            result = ActionResult.from_dict(action["result"])
            formatted = ActionResultFormatter.to_html(result)
            html.append(formatted)
            html.append("<hr>")

        html.append("</body></html>")
        return "\n".join(html)

    @classmethod
    def from_record(cls, record: "JobRecord") -> "JobResult":
        """Create JobResult from database record"""
        result = cls(success=record.success, message=record.message, data=record.data)
        if record.outputs:
            result.outputs = record.outputs
        return result


class Job(DBSessionMixin, ABC):
    """Base class for background jobs"""

    def __init__(self, job_type: str):
        DBSessionMixin.__init__(self)
        self.id = str(uuid.uuid4())
        self.type = job_type
        self.status = JobStatus.PENDING
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.result: Optional[JobResult] = None
        self.error: Optional[str] = None
        self.logger = Logger(self.__class__.__name__)
        self.notification_service = DatabaseNotificationService()

    def _store_in_db(self) -> None:
        """Store job details in database"""
        try:
            with self.get_session() as session:
                job_record = session.query(JobRecord).filter(JobRecord.id == self.id).first()
                if not job_record:
                    job_record = JobRecord()
                    job_record.id = self.id
                    session.add(job_record)

                job_record.type = self.type
                job_record.status = self.status.value
                job_record.started_at = self.started_at
                job_record.completed_at = self.completed_at
                job_record.success = self.result.success if self.result else None
                job_record.message = self.result.message if self.result else None
                job_record.data = self.result.data if self.result else None
                job_record.outputs = self.result.outputs if self.result else []

                session.commit()

        except Exception as e:
            self.logger.error(f"Failed to store job in database: {e}")

    async def _notify_status(self, message: str) -> None:
        """Send a notification about job status"""
        try:
            await self.notification_service.send_message(f"Job {self.id} ({self.type}): {message}")
        except Exception as e:
            self.logger.error(f"Failed to send job notification: {e}")

    @abstractmethod
    async def start(self) -> None:
        """Start the job. Must be implemented by subclasses."""

    @abstractmethod
    async def stop_handler(self) -> None:
        """Handle cleanup operations when stopping the job. Must be implemented by subclasses.

        This method should handle any job-specific cleanup operations such as:
        - Stopping external processes
        - Cleaning up temporary files
        - Closing network connections
        - Releasing resources
        """

    async def stop(self) -> None:
        """Stop the job and perform cleanup.

        This method first calls the job-specific stop_handler for cleanup,
        then marks the job as cancelled.
        """
        await self.stop_handler()
        await self.cancel()

    async def complete(self, result: JobResult) -> None:
        """Mark job as completed with result"""
        self.completed_at = datetime.utcnow()
        self.status = JobStatus.COMPLETED
        self.result = result
        self._store_in_db()
        await self._notify_status(f"✅ Completed. Use /job {self.id} to view results")

    async def fail(self, error: str) -> None:
        """Mark job as failed with error"""
        self.completed_at = datetime.utcnow()
        self.status = JobStatus.FAILED
        self.error = error
        self.result = JobResult(success=False, message=error)
        self._store_in_db()
        await self._notify_status(f"❌ Failed. Use /job {self.id} for details")

    async def cancel(self) -> None:
        """Mark job as cancelled"""
        self.completed_at = datetime.utcnow()
        self.status = JobStatus.CANCELLED
        self._store_in_db()
        await self._notify_status(f"⚠️ Cancelled. Use /job {self.id} for details")

    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary"""
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result.get_output() if self.result else None,
            "error": self.error,
            "outputs": self.result.outputs if self.result else None,
            "message": self.result.message if self.result else None,
            "data": self.result.data if self.result else None,
        }

    @classmethod
    def from_record(cls, record: JobRecord) -> "Job":
        """Create Job instance from database record"""
        # Import here to avoid circular imports
        from src.jobs.manager import JobManager

        # Get job class from manager
        job_class = JobManager.get_job_class(record.type)
        if not job_class:
            raise ValueError(f"Unknown job type: {record.type}")

        # Create job instance with appropriate constructor arguments
        if record.data:
            job = job_class(**record.data)
        else:
            job = job_class()

        # Restore job state
        job.id = record.id
        job.status = JobStatus(record.status)
        job.started_at = record.started_at
        job.completed_at = record.completed_at

        if record.success is not None:
            job.result = JobResult.from_record(record)

        return job
