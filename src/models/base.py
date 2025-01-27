from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship, backref
from sqlalchemy.types import UserDefinedType
from src.backend.database import Base
import enum
from datetime import datetime
import os
from typing import Optional


# Add custom VECTOR type for pgvector
class VECTOR(UserDefinedType):
    def __init__(self, dimensions):
        self.dimensions = dimensions

    def get_col_spec(self):
        return f"vector({self.dimensions})"

    def bind_processor(self, dialect):
        def process(value):
            if value is None:
                return None
            if isinstance(value, (list, tuple)):
                if len(value) != self.dimensions:
                    raise ValueError(f"Vector must have exactly {self.dimensions} dimensions")
                # Let PostgreSQL handle the array-to-vector cast
                return value
            return value

        return process

    def result_processor(self, dialect, coltype):
        def process(value):
            if value is None:
                return None
            # pgvector returns the data as a native array
            return value

        return process


class AssetType(str, enum.Enum):
    GITHUB_REPO = "github_repo"
    GITHUB_FILE = "github_file"
    DEPLOYED_CONTRACT = "deployed_contract"
    LOCAL_IMPORT = "local_import"


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
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    identifier = Column(String, unique=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    asset_type = Column(String)
    source_url = Column(String)
    local_path = Column(String)
    extra_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    embedding = Column(VECTOR(384), nullable=True)  # For MiniLM-L6-v2 embeddings

    # Implementation id for proxy contracts
    implementation_id = Column(Integer, ForeignKey("assets.id"), nullable=True)

    # One-to-many relationship:
    # One implementation can have many proxies pointing to it
    implementation = relationship(
        "Asset", foreign_keys=[implementation_id], backref=backref("proxy_contracts", lazy="dynamic"), remote_side=[id]
    )

    # Proxy status flags
    is_proxy = Column(Boolean, default=False)
    checked_for_proxy = Column(Boolean, default=False)

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
            "is_proxy": self.is_proxy,
            "checked_for_proxy": self.checked_for_proxy,
        }

    def generate_embedding_text(self) -> Optional[str]:
        """Generate enriched text for embedding generation."""
        code = self.get_code()
        if not code:
            return None

        text_parts = []

        # Add high-level context with more detailed type checking
        if hasattr(self, "project") and self.project is not None:
            if isinstance(self.project, type):
                print(f"Error: project is a class instead of an instance for asset {self.id}")
            elif not isinstance(self.project, Project):
                print(f"Error: project is type {type(self.project)} for asset {self.id}")
            else:
                text_parts.append(f"Project: {self.project.name}")
                if self.project.description:
                    text_parts.append(f"Context: {self.project.description}")

        # Add the code with some basic context
        text_parts.append(f"Type: {self.asset_type}")
        text_parts.append("Content:")
        text_parts.append(code)

        return "\n".join(text_parts)

    def get_code(self) -> Optional[str]:
        """Get code contents for the asset.

        Returns:
            str: Code contents for GITHUB_FILE and DEPLOYED_CONTRACT assets
            None: If asset type is not supported or file cannot be read
        """
        if not self.local_path or not os.path.exists(self.local_path):
            return None

        try:
            if self.asset_type == AssetType.GITHUB_FILE:
                return self._read_file_contents(self.local_path)
            elif self.asset_type == AssetType.DEPLOYED_CONTRACT:
                if not os.path.isdir(self.local_path):
                    return None
                return self._read_directory_contents(self.local_path)
            return None

        except Exception as e:
            # Log error but don't raise - return None to indicate failure
            print(f"Error reading code for asset {self.id}: {str(e)}")
            return None

    def _read_file_contents(self, path: str) -> str:
        """Read contents of a single file"""
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def _read_directory_contents(self, directory: str) -> str:
        """Read and concatenate contents of all files in directory"""
        contents = []

        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    relative_path = os.path.relpath(file_path, directory)
                    file_content = self._read_file_contents(file_path)
                    contents.append(f"// File: {relative_path}\n{file_content}\n")
                except Exception:
                    continue  # Skip files that can't be read

        return "\n".join(contents)

    def is_implementation(self) -> bool:
        """Check if this is an implementation contract"""
        return self.asset_type == AssetType.DEPLOYED_CONTRACT and bool(self.proxy_contracts)

    def refresh_from_session(self, session):
        """Refresh the object from the database"""
        session.refresh(self)

    def mark_as_non_proxy(self, session):
        """Mark asset as non-proxy and commit"""
        self.checked_for_proxy = True
        self.is_proxy = False
        session.add(self)
        session.commit()
        session.refresh(self)  # Refresh after commit

    def mark_as_proxy(self, session, implementation=None):
        """Mark asset as proxy and set implementation"""
        self.checked_for_proxy = True
        self.is_proxy = True
        if implementation:
            self.implementation = implementation
        session.add(self)
        session.commit()
        session.refresh(self)  # Refresh after commit
