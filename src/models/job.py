from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from src.backend.database import Base

class JobRecord(Base):
    """Database record for jobs"""
    __tablename__ = 'jobs'
    
    id = Column(String, primary_key=True)
    type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    success = Column(Boolean, nullable=True)
    message = Column(String, nullable=True)
    data = Column(JSON, nullable=True)
    outputs = Column(JSON, nullable=True)  # List of string outputs
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @classmethod
    def from_job(cls, job):
        """Create record from Job instance"""
        result = job.result or {}
        return cls(
            id=job.id,
            type=job.type.value,
            status=job.status.value,
            started_at=job.started_at,
            completed_at=job.completed_at,
            success=result.success if result else None,
            message=result.message if result else None,
            data=result.data if result else None,
            outputs=result.outputs if result else []
        ) 