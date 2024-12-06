from sqlalchemy import Column, String, DateTime, Integer
from datetime import datetime
from src.backend.database import Base

class GitHubRepoState(Base):
    """Model for tracking GitHub repository states.
    
    This model keeps track of the last known state of GitHub repositories being monitored,
    including the last processed commit SHA and PR number to avoid duplicate processing.
    """
    __tablename__ = "github_repo_state"
    
    repo_url = Column(String, primary_key=True)  # Normalized repo URL
    last_commit_sha = Column(String)  # Last processed commit SHA
    last_pr_number = Column(Integer)  # Last processed PR number
    last_check = Column(DateTime)  # Last time we checked this repo
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert model instance to dictionary representation.
        
        Returns:
            dict: Dictionary containing model data with datetime fields converted to ISO format
        """
        return {
            'repo_url': self.repo_url,
            'last_commit_sha': self.last_commit_sha,
            'last_pr_number': self.last_pr_number,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        } 