from sqlalchemy import Column, String, DateTime, JSON
from datetime import datetime
from src.backend.database import Base


class EventLog(Base):
    """Model for storing event handler execution logs"""

    __tablename__ = "event_logs"

    id = Column(String, primary_key=True)
    handler_name = Column(String, nullable=False)
    trigger = Column(String, nullable=False)
    result = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.created_at is None:
            self.created_at = datetime.utcnow()
