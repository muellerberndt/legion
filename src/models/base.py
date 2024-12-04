from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Table, JSON, ARRAY, Float
from sqlalchemy.orm import relationship
from src.backend.database import Base
import enum
from datetime import datetime
import os
import logging

class AssetType(str, enum.Enum):
    GITHUB_REPO = "github_repo"
    GITHUB_FILE = "github_file"
    DEPLOYED_CONTRACT = "deployed_contract"

class LogLevel(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

# Association table for project-asset relationship
project_assets = Table(
    'project_assets',
    Base.metadata,
    Column('project_id', Integer, ForeignKey('projects.id')),
    Column('asset_id', String, ForeignKey('assets.id'))
)

class Project(Base):
    """Project model"""
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String)
    project_type = Column(String, nullable=False)  # e.g., "immunefi"
    languages = Column(JSON)  # List of programming languages
    features = Column(JSON)  # Project features/tags
    extra_data = Column(JSON)  # Additional platform-specific data
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    assets = relationship("Asset", secondary=project_assets, back_populates="projects")

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'project_type': self.project_type,
            'languages': self.languages,
            'features': self.features,
            'extra_data': self.extra_data,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Asset(Base):
    """Asset model"""
    __tablename__ = "assets"
    
    id = Column(String, primary_key=True)  # URL or unique identifier
    asset_type = Column(String)  # Type of asset (repo, file, contract)
    file_url = Column(String)  # For individual files
    repo_url = Column(String)  # For repositories
    explorer_url = Column(String)  # For deployed contracts
    local_path = Column(String)  # Path to downloaded content
    extra_data = Column(JSON)  # Additional metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Vector embedding for semantic search
    embedding = Column(ARRAY(Float), nullable=True)  # 1536-dimensional vector
    
    # Relationships
    projects = relationship("Project", secondary=project_assets, back_populates="assets")

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'asset_type': self.asset_type,
            'file_url': self.file_url,
            'repo_url': self.repo_url,
            'explorer_url': self.explorer_url,
            'local_path': self.local_path,
            'extra_data': self.extra_data,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
    def generate_embedding_text(self) -> str:
        """Generate text for embedding from asset contents"""
        if not self.local_path:
            return ""  # Can't generate embedding without local content
            
        try:
            if self.asset_type == AssetType.GITHUB_FILE:
                # For single files, use the file content directly
                with open(self.local_path, 'r', encoding='utf-8') as f:
                    return f.read()
                    
            elif self.asset_type == AssetType.GITHUB_REPO:
                # For repositories, try to use README first
                readme_paths = [
                    os.path.join(self.local_path, 'README.md'),
                    os.path.join(self.local_path, 'README'),
                    os.path.join(self.local_path, 'readme.md')
                ]
                for path in readme_paths:
                    if os.path.exists(path):
                        with open(path, 'r', encoding='utf-8') as f:
                            return f.read()
                            
                # If no README, try to find and use main contract file
                if os.path.isdir(self.local_path):
                    for root, _, files in os.walk(self.local_path):
                        for file in files:
                            if file.endswith('.sol'):
                                file_path = os.path.join(root, file)
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    return f.read()
                                    
            return ""  # Return empty string if no content could be extracted
            
        except Exception as e:
            logging.getLogger("Asset").error(f"Failed to generate embedding text for {self.id}: {str(e)}")
            return ""

class LogEntry(Base):
    """Model for storing application logs"""
    __tablename__ = 'logs'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    level = Column(String, nullable=False)
    message = Column(String, nullable=False)
    source = Column(String)  # Component/module that generated the log
    extra_data = Column(JSON)  # For additional context/data