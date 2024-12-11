from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid
from src.util.logging import Logger
from src.models.job import JobRecord
from src.backend.database import DBSessionMixin
from abc import ABC, abstractmethod


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(Enum):
    """Types of jobs"""

    AGENT = "agent"
    INDEXER = "indexer"
    SCAN = "scan"  # For security scanning jobs
    # Add more job types as needed


class JobResult(DBSessionMixin):
    """Result of a job execution"""

    # Maximum length for Telegram messages
    MAX_MESSAGE_LENGTH = 4096

    def __init__(self, success: bool = True, message: str = "", data: Dict = None):
        DBSessionMixin.__init__(self)
        self.success = success
        self.message = message
        self.data = data or {}
        self.outputs: List[str] = []
        self.logger = Logger("JobResult")

    def add_output(self, output: str) -> None:
        """Add an output line"""
        self.outputs.append(output)

    def get_output(self) -> str:
        """Get the complete output"""
        if not self.outputs:
            return self.message or "No output"

        return "\n".join(self.outputs)


class Job(DBSessionMixin, ABC):
    """Base class for background jobs"""

    def __init__(self, job_type: JobType):
        DBSessionMixin.__init__(self)
        self.id = str(uuid.uuid4())
        self.type = job_type
        self.status = JobStatus.PENDING
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.result: Optional[JobResult] = None
        self.error: Optional[str] = None
        self.logger = Logger(self.__class__.__name__)

    def _store_in_db(self) -> None:
        """Store job details in database"""
        try:
            with self.get_session() as session:
                job_record = session.query(JobRecord).filter(JobRecord.id == self.id).first()
                if not job_record:
                    job_record = JobRecord()
                    job_record.id = self.id
                    session.add(job_record)

                job_record.type = self.type.value
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

    @abstractmethod
    async def start(self) -> None:
        """Start the job. Must be implemented by subclasses."""
        pass

    @abstractmethod
    async def stop_handler(self) -> None:
        """Handle cleanup operations when stopping the job. Must be implemented by subclasses.

        This method should handle any job-specific cleanup operations such as:
        - Stopping external processes
        - Cleaning up temporary files
        - Closing network connections
        - Releasing resources
        """
        pass

    async def stop(self) -> None:
        """Stop the job and perform cleanup.

        This method first calls the job-specific stop_handler for cleanup,
        then marks the job as cancelled.
        """
        await self.stop_handler()
        await self.cancel()

    def complete(self, result: JobResult) -> None:
        """Mark job as completed with result"""
        self.completed_at = datetime.utcnow()
        self.status = JobStatus.COMPLETED
        self.result = result
        self._store_in_db()

    def fail(self, error: str) -> None:
        """Mark job as failed with error"""
        self.completed_at = datetime.utcnow()
        self.status = JobStatus.FAILED
        self.error = error
        self._store_in_db()

    async def cancel(self) -> None:
        """Mark job as cancelled"""
        self.completed_at = datetime.utcnow()
        self.status = JobStatus.CANCELLED
        self._store_in_db()

    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary"""
        return {
            "id": self.id,
            "type": self.type.value,
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
        from src.jobs.agent import AgentJob
        from src.jobs.indexer import IndexerJob

        # Map job types to classes
        job_classes = {JobType.AGENT: AgentJob, JobType.INDEXER: IndexerJob}

        # Get the appropriate job class
        job_type = JobType(record.type)
        job_class = job_classes.get(job_type)
        if not job_class:
            raise ValueError(f"Unknown job type: {record.type}")

        # Create job instance
        if job_type == JobType.AGENT:
            job = job_class(prompt=record.data.get("prompt", ""))
        else:
            job = job_class(platform=record.data.get("platform", ""))

        # Restore job state
        job.id = record.id
        job.status = JobStatus(record.status)
        job.started_at = record.started_at
        job.completed_at = record.completed_at

        if record.success is not None:
            job.result = JobResult.from_record(record)

        return job
