import pytest
from unittest.mock import Mock, patch, mock_open
from src.jobs.file_search import FileSearchJob
from src.util.logging import LogConfig
from src.models.base import Asset
from src.jobs.base import JobStatus
from src.config.config import Config
import os
import re
from unittest.mock import AsyncMock


@pytest.fixture
def mock_session():
    session = Mock()

    # Create mock assets
    mock_asset1 = Mock(spec=Asset)
    mock_asset1.local_path = "/path/to/test1.sol"
    mock_asset2 = Mock(spec=Asset)
    mock_asset2.local_path = "/path/to/test2.cairo"
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


@pytest.fixture
def mock_config():
    """Mock Config class"""
    with patch("src.jobs.file_search.Config") as config_mock:
        # Create a mock instance
        instance = Mock()
        instance.get.return_value = [".sol", ".cairo", ".rs"]

        # Make the Config constructor return our mock instance
        config_mock.return_value = instance

        yield config_mock


def test_extension_filtering(mock_config):
    """Test file extension filtering"""
    job = FileSearchJob(regex_pattern="test")

    # Should accept allowed extensions
    assert not job._should_skip_file("test.sol")
    assert not job._should_skip_file("test.cairo")
    assert not job._should_skip_file("test.rs")

    # Should skip non-allowed extensions
    assert job._should_skip_file("test.js")
    assert job._should_skip_file("test.py")

    # Should skip binary and archive extensions
    assert job._should_skip_file("test.exe")
    assert job._should_skip_file("test.zip")
    assert job._should_skip_file("test.jpg")


def test_file_content_search(mock_config):
    """Test file content searching with context"""
    test_content = "This is a test file.\nIt contains a pattern to match.\nAnd some more content."

    # Create a mock file object
    mock_file = mock_open(read_data=test_content)

    with (
        patch("builtins.open", mock_file),
        patch("src.jobs.file_search.is_binary_file", return_value=False),  # Ensure binary check passes
    ):
        job = FileSearchJob(regex_pattern="pattern")
        matches = job._search_file("test.sol", job.pattern)

        assert len(matches) == 1
        match = matches[0]
        assert "pattern" in match["match"]
        assert "context" in match
        assert len(match["context"]) <= 100  # Context should be limited


@pytest.mark.asyncio
async def test_binary_file_handling(mock_session, mock_config):
    """Test handling of binary files"""

    def mock_is_binary(file_path):
        return file_path.endswith(".bin")

    with (
        patch("src.backend.database.DBSessionMixin.get_session", return_value=mock_session),
        patch("src.jobs.file_search.is_binary_file", side_effect=mock_is_binary),
        patch("os.path.exists", return_value=True),
    ):
        job = FileSearchJob(regex_pattern="test")

        # Binary file should be skipped
        result = job._search_file("test.bin", job.pattern)
        assert len(result) == 0

        # Text file should be processed
        with patch("builtins.open", mock_open(read_data="test content")):
            result = job._search_file("test.sol", job.pattern)
            assert len(result) > 0


@pytest.mark.asyncio
async def test_directory_search(mock_config):
    """Test recursive directory searching"""
    mock_files = {
        "test1.sol": "contract Test { function test() public {} }",
        "test2.cairo": "func test() { return (); }",
        "test3.txt": "should be skipped",
        "test4.bin": "binary content",
    }

    def mock_walk(directory):
        yield directory, [], list(mock_files.keys())

    def mock_open_file(file_path, mode="r"):
        if file_path.endswith(".bin"):
            return mock_open(read_data=b"\x00\x01\x02")(file_path, mode)
        basename = os.path.basename(file_path)
        content = mock_files.get(basename, "")
        m = mock_open(read_data=content)
        return m(file_path, mode)

    with (
        patch("os.walk", side_effect=mock_walk),
        patch("builtins.open", side_effect=mock_open_file),
        patch("src.jobs.file_search.is_binary_file", return_value=False),  # Ensure binary check passes
    ):
        job = FileSearchJob(regex_pattern="test")
        matches = job._search_directory("/test/dir", job.pattern)

        # Should find matches in .sol and .cairo files
        assert len(matches) == 2
        file_paths = [match["file_path"] for match in matches]
        assert any("test1.sol" in path for path in file_paths)
        assert any("test2.cairo" in path for path in file_paths)
