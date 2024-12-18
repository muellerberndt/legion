import pytest
from unittest.mock import patch, MagicMock
from src.jobs.embed import EmbedJob
from src.models.base import Asset
from src.jobs.base import JobStatus


def create_mock_asset(i):
    """Create a mock asset"""
    asset = Asset()
    asset.id = str(i)
    asset.asset_type = "github_file"
    asset.local_path = f"/path/to/asset_{i}"
    asset.embedding = None
    # Store the generate_embedding_text function as an instance attribute
    asset._test_id = str(i)  # Store id for the text generation
    asset.generate_embedding_text = lambda self=asset: f"Test content for asset {self._test_id}"
    return asset


class MockSession:
    """Custom session mock to ensure consistent behavior"""

    def __init__(self):
        self.commit_calls = []
        self.execute_calls = []
        self.rollback_calls = []
        self.assets = [create_mock_asset(i) for i in range(15)]

        # Set up execute mock
        self.execute = MagicMock()
        self.execute.return_value.scalars.return_value.all.return_value = self.assets

    def commit(self):
        """Track commit calls and optionally raise errors"""
        self.commit_calls.append(len(self.commit_calls) + 1)
        if hasattr(self, "commit_error") and len(self.commit_calls) == 2:
            raise Exception("Database error on second batch")

    def rollback(self):
        """Track rollback calls"""
        self.rollback_calls.append(len(self.rollback_calls) + 1)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return None


@pytest.mark.asyncio
async def test_embed_job():
    """Test embedding job execution with batching"""
    session = MockSession()
    mock_embedding = [0.1] * 384  # Mock embedding vector with correct dimension

    with (
        patch("src.backend.database.DBSessionMixin.get_session", return_value=session),
        patch("src.util.embeddings.generate_embedding", return_value=mock_embedding),
        patch("os.path.isdir", return_value=False),
        patch("sqlalchemy.orm.object_session", return_value=session),
        patch("src.util.embeddings.object_session", return_value=session),
    ):
        job = EmbedJob()
        await job.start()

        # Verify job completed successfully
        assert job.status == JobStatus.COMPLETED
        assert job.result.success is True
        assert job.processed == 15  # All mock assets were processed
        assert job.failed == 0  # No failures

        # With 15 assets and batch size of 10:
        # - First batch of 10 -> commit
        # - Final batch of 5 -> commit
        expected_commits = 2
        assert (
            len(session.commit_calls) == expected_commits
        ), f"Expected {expected_commits} commits (2 batches), got {len(session.commit_calls)}. Commit calls: {session.commit_calls}"

        assert "Generated embeddings for 15 assets" in job.result.message
