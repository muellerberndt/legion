from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional, List, Type
from datetime import datetime
import uuid
from dataclasses import dataclass
from src.util.logging import Logger
from src.models.job import JobRecord

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
    WATCHER = "watcher"
    SCAN = "scan"  # For security scanning jobs
    # Add more job types as needed

class JobResult:
    """Result of a job execution"""
    def __init__(self, success: bool, message: str, data: Optional[Dict[str, Any]] = None):
        self.success = success
        self.message = message
        self.data = data or {}
        self.outputs: List[str] = []  # Store chronological outputs
        self.created_at = datetime.utcnow()
    
    def add_output(self, output: str) -> None:
        """Add output to the result history"""
        if output:  # Only add non-empty outputs
            self.outputs.append(output)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'message': self.message,
            'data': self.data,
            'outputs': self.outputs,
            'created_at': self.created_at.isoformat()
        }

    @classmethod
    def from_record(cls, record: JobRecord) -> 'JobResult':
        """Create JobResult from database record"""
        result = cls(
            success=record.success or False,
            message=record.message or "",
            data=record.data or {}
        )
        result.outputs = record.outputs or []
        return result

class Job(ABC):
    """Base class for long-running jobs"""
    
    def __init__(self, job_type: JobType):
        self.id = str(uuid.uuid4())
        self.type = job_type
        self.status = JobStatus.PENDING
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.result: Optional[JobResult] = None
        self.error: Optional[str] = None
        self.logger = Logger(self.__class__.__name__)
        
    @abstractmethod
    async def start(self) -> None:
        """Start the job"""
        pass
        
    @abstractmethod
    async def stop(self) -> None:
        """Stop the job"""
        pass
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary for status reporting"""
        return {
            'id': self.id,
            'type': self.type,
            'status': self.status,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'result': self.result.to_dict() if self.result else None,
            'error': self.error
        }

    @classmethod
    def from_record(cls, record: JobRecord) -> 'Job':
        """Create Job instance from database record"""
        # Import here to avoid circular imports
        from src.jobs.agent import AgentJob
        from src.jobs.indexer import IndexerJob
        
        # Map job types to classes
        job_classes = {
            JobType.AGENT: AgentJob,
            JobType.INDEXER: IndexerJob
        }
        
        # Get the appropriate job class
        job_type = JobType(record.type)
        job_class = job_classes.get(job_type)
        if not job_class:
            raise ValueError(f"Unknown job type: {record.type}")
            
        # Create job instance
        if job_type == JobType.AGENT:
            job = job_class(prompt=record.data.get('prompt', ''))
        else:
            job = job_class(platform=record.data.get('platform', ''))
            
        # Restore job state
        job.id = record.id
        job.status = JobStatus(record.status)
        job.started_at = record.started_at
        job.completed_at = record.completed_at
        
        if record.success is not None:
            job.result = JobResult.from_record(record)
            
        return job