import pytest
from unittest.mock import Mock, patch
from src.jobs.file_search import FileSearchJob
from src.util.logging import LogConfig
from src.models.base import Asset
from src.jobs.base import JobStatus


@pytest.fixture
def mock_session():
    session = Mock()

    # Create mock assets
    mock_asset1 = Mock(spec=Asset)
    mock_asset1.local_path = "/path/to/test1.txt"
    mock_asset2 = Mock(spec=Asset)
    mock_asset2.local_path = "/path/to/test2.txt"
    mock_assets = [mock_asset1, mock_asset2]

    # Set up the chain of mock calls
    mock_execute = Mock()
    mock_scalars = Mock()
    mock_scalars.all.return_value = mock_assets
    mock_execute.scalars.return_value = mock_scalars
    session.execute.return_value = mock_execute

    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=None)
    return session


# Set log level to DEBUG for tests
LogConfig.set_log_level("DEBUG")


@pytest.mark.asyncio
async def test_file_search_job(mock_session):
    """Test file search job execution"""
    with (
        patch("src.backend.database.DBSessionMixin.get_session", return_value=mock_session),
        patch("os.path.exists", return_value=True),
    ):  # Mock os.path.exists to return True
        job = FileSearchJob(regex_pattern="test.*pattern")
        await job.start()

        # Verify job completed successfully
        assert job.status.value == JobStatus.COMPLETED.value
        assert job.result.success is True
