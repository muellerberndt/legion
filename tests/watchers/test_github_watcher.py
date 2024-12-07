import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone, timedelta
from src.watchers.github import GitHubWatcher
from src.util.logging import Logger
from src.jobs.watcher import WatcherJob
from src.backend.database import DBSessionMixin

logger = Logger("TestGitHubWatcher")


@pytest.fixture
async def mock_session():
    """Mock aiohttp ClientSession"""
    session = AsyncMock()
    session.get = AsyncMock()
    yield session


@pytest.fixture
async def mock_db_session():
    """Mock database session"""
    session = AsyncMock()

    # Create a mock repo state that will be returned by get()
    repo_state = Mock()
    repo_state.last_commit_sha = "old-sha"
    repo_state.last_pr_number = 1

    # Set up the get method to return our mock state
    async def get_mock(model_class, key):
        logger.debug(f"Mock get called with: {model_class=}, {key=}")
        if key == "https://github.com/owner/repo":
            logger.debug("Returning mock repo state")
            return repo_state
        logger.debug("Returning None")
        return None

    session.get = AsyncMock(side_effect=get_mock)
    session.add = AsyncMock()
    session.commit = AsyncMock()

    # Set up context manager
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    yield session


@pytest.fixture
async def watcher(mock_session, mock_db_session):
    """Create a GitHub watcher instance"""
    with (
        patch("src.watchers.github.Config") as MockConfig,
        patch("src.backend.database.DBSessionMixin.get_async_session") as mock_get_session,
        patch("aiohttp.ClientSession", return_value=mock_session),
    ):
        # Create a mock instance
        mock_config = Mock()
        mock_config.get.return_value = {"poll_interval": 300, "api_token": "test-token"}
        MockConfig.return_value = mock_config

        # Create a mock context manager
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_db_session)
        cm.__aexit__ = AsyncMock(return_value=None)
        mock_get_session.return_value = cm

        # Create watcher and initialize it
        watcher = GitHubWatcher()
        # Initialize parent classes manually since we're not using super()
        WatcherJob.__init__(watcher, "github", 300)
        DBSessionMixin.__init__(watcher)

        # Mock the handler registry's trigger_event method
        watcher.handler_registry.trigger_event = AsyncMock()

        await watcher.initialize()  # This will now use our mock session

        yield watcher

        # Clean up
        await watcher.stop()


@pytest.mark.asyncio
async def test_no_updates(watcher, mock_session, mock_db_session):
    """Test when there are no updates"""
    # Mock repo data with recent updates
    repo = {
        "repo_url": "https://github.com/owner/repo",
        "last_commit_sha": "current-sha",
        "last_pr_number": 2,
        "last_check": datetime.now(timezone.utc) - timedelta(minutes=5),
    }

    # Mock API responses with no new data
    commits_response = AsyncMock()
    commits_response.status = 200
    commits_response.json.return_value = [{"sha": "current-sha", "commit": {"message": "Old commit"}}]

    prs_response = AsyncMock()
    prs_response.status = 200
    prs_response.json.return_value = [
        {"number": 2, "title": "Old PR", "updated_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}
    ]

    # Set up session mock
    mock_session.get = AsyncMock()
    mock_session.get.side_effect = [commits_response, prs_response]

    # Mock the database session context manager
    with patch("src.backend.database.DBSessionMixin.get_async_session") as mock_get_session:
        mock_get_session.return_value.__aenter__.return_value = mock_db_session

        # Check for updates
        await watcher._check_repo_updates(repo)

        # Verify no events were triggered
        assert not watcher.handler_registry.trigger_event.called


@pytest.mark.asyncio
async def test_api_error_handling(watcher, mock_session, mock_db_session):
    """Test handling API errors gracefully"""
    # Mock repo data
    repo = {"repo_url": "https://github.com/owner/repo", "last_commit_sha": None, "last_pr_number": None, "last_check": None}

    # Mock API error responses
    error_response = AsyncMock()
    error_response.status = 403
    mock_session.get = AsyncMock(return_value=error_response)

    # Mock the database session context manager
    with patch("src.backend.database.DBSessionMixin.get_async_session") as mock_get_session:
        mock_get_session.return_value.__aenter__.return_value = mock_db_session

        # Check for updates
        await watcher._check_repo_updates(repo)

        # Verify no events were triggered
        assert not watcher.handler_registry.trigger_event.called


@pytest.mark.asyncio
async def test_parse_repo_url():
    """Test parsing GitHub repository URLs"""
    watcher = GitHubWatcher()

    # Test valid URL
    owner, repo = watcher._parse_repo_url("https://github.com/owner/repo")
    assert owner == "owner"
    assert repo == "repo"

    # Test URL with extra parts
    owner, repo = watcher._parse_repo_url("https://github.com/owner/repo/tree/main")
    assert owner == "owner"
    assert repo == "repo"

    # Test invalid URL
    owner, repo = watcher._parse_repo_url("https://not-github.com/owner/repo")
    assert owner is None
    assert repo is None
