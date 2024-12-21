from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from src.backend.database import Base
import enum
from datetime import datetime
import os
import json


class AssetType(str, enum.Enum):
    GITHUB_REPO = "github_repo"
    GITHUB_FILE = "github_file"
    DEPLOYED_CONTRACT = "deployed_contract"


class Project(Base):
    """Project model"""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String)
    project_type = Column(String, nullable=False)  # e.g., "bounty"
    project_source = Column(String, nullable=False)  # e.g., "immunefi"
    source_url = Column(String)  # URL to project source/listing
    keywords = Column(JSON)  # Project keywords/tags
    extra_data = Column(JSON)  # Additional platform-specific data
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # One-to-many relationship
    assets = relationship("Asset", back_populates="project")

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "project_type": self.project_type,
            "project_source": self.project_source,
            "source_url": self.source_url,
            "keywords": self.keywords,
            "extra_data": self.extra_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Asset(Base):
    """Asset model"""

    __tablename__ = "assets"

    id = Column(Integer, primary_key=True)
    identifier = Column(String, unique=True)  # URL or unique identifier
    project_id = Column(Integer, ForeignKey("projects.id"))
    asset_type = Column(String)  # Type of asset (repo, file, contract)
    source_url = Column(String)  # URL to asset source
    local_path = Column(String)  # Path to downloaded content
    extra_data = Column(JSON)  # Additional metadata including asset-specific URLs
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    embedding = Column(String)  # Store as string, let Postgres handle vector conversion

    # Many-to-one relationship
    project = relationship("Project", back_populates="assets")

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "identifier": self.identifier,
            "project_id": self.project_id,
            "asset_type": self.asset_type,
            "source_url": self.source_url,
            "local_path": self.local_path,
            "extra_data": self.extra_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def generate_embedding_text(self) -> str:
        """Generate text for embedding"""
        text_parts = []

        # Add basic info
        if self.source_url:
            text_parts.append(f"Source: {self.source_url}")

        # Add metadata if available
        if self.extra_data:
            try:
                if isinstance(self.extra_data, str):
                    metadata = json.loads(self.extra_data)
                else:
                    metadata = self.extra_data

                # Add relevant metadata fields
                if "description" in metadata:
                    text_parts.append(metadata["description"])
                if "name" in metadata:
                    text_parts.append(metadata["name"])
            except Exception:
                pass

        # Add file contents if available
        if self.local_path and os.path.exists(self.local_path):
            try:
                with open(self.local_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    text_parts.append(content)
            except Exception:
                pass

        return "\n".join(text_parts)
