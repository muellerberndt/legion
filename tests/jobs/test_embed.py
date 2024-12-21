import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.jobs.embed import EmbedJob
from src.models.base import Asset, Project
from src.backend.database import db
import numpy as np
from sqlalchemy.orm import Session


@pytest.fixture
def mock_database():
    """Create a mock database with proper session handling"""
    with patch("src.backend.database.Database") as mock_db:
        # Create a session that can handle our test data
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        # Make get_session return our mock session
        mock_db.session.return_value.__enter__.return_value = session
        mock_db.get_session = lambda: session

        yield mock_db


@pytest.fixture
def test_db_session(mock_database):
    """Create a test database session with test data"""
    session = MagicMock()

    # Set up test data
    test_asset = Asset(
        identifier="test_asset", project_id=1, asset_type="test", source_url="http://test.com", local_path="/tmp/test.txt"
    )

    # Make the session return our test data
    session.execute.return_value.scalars.return_value.all.return_value = [test_asset]

    yield session


@pytest.fixture
def mock_embedding():
    return [0.1] * 384  # Create a 384-dimensional test embedding


@pytest.fixture
def mock_generate_embedding(mock_embedding):
    async def async_return(*args, **kwargs):
        return mock_embedding

    with patch("src.util.embeddings.generate_embedding", new_callable=AsyncMock) as mock:
        mock.side_effect = async_return
        yield mock


async def test_embed_job(test_db_session, mock_generate_embedding, mock_embedding):
    # Create and run the job
    job = EmbedJob()

    # Mock the session creation in the job
    with patch.object(job, "get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = test_db_session

        # Run the job
        await job.start()

        # Verify the job completed successfully
        assert job.processed > 0
        assert job.failed == 0

        # Verify the mock was called
        mock_generate_embedding.assert_called()

        # Verify the database
