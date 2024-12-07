import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone, timedelta
from src.watchers.github import GitHubWatcher
from src.util.logging import Logger
from src.handlers.base import HandlerTrigger

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


@pytest.fixture
def watcher():
    watcher = GitHubWatcher()
    watcher.handler_registry.trigger_event = AsyncMock()
    return watcher


@pytest.mark.asyncio
async def test_check_repo_updates_triggers_events_with_payload(watcher):
    """Test that GitHub events are triggered with the correct payload structure"""
    # Mock the API responses
    test_commit = {
        "sha": "abc123",
        "commit": {"message": "Test commit", "author": {"name": "Test Author"}},
        "html_url": "https://github.com/test/repo/commit/abc123",
    }
    test_pr = {
        "number": 1,
        "title": "Test PR",
        "user": {"login": "test-user"},
        "html_url": "https://github.com/test/repo/pull/1",
    }

    # Mock the API calls
    watcher._get_new_commits = AsyncMock(return_value=[test_commit])
    watcher._get_updated_prs = AsyncMock(return_value=[test_pr])
    watcher._update_repo_state = AsyncMock()

    # Test data
    repo = {
        "repo_url": "https://github.com/test/repo",
        "last_commit_sha": None,  # No previous commits
        "last_pr_number": None,  # No previous PRs
        "last_check": None,
    }

    # Run the update check
    await watcher._check_repo_updates(repo)

    # Verify push event was triggered with correct payload structure
    watcher.handler_registry.trigger_event.assert_any_call(
        HandlerTrigger.GITHUB_PUSH, {"payload": {"repo_url": repo["repo_url"], "commit": test_commit}}
    )

    # Verify PR event was triggered with correct payload structure
    watcher.handler_registry.trigger_event.assert_any_call(
        HandlerTrigger.GITHUB_PR, {"payload": {"repo_url": repo["repo_url"], "pull_request": test_pr}}
    )

    # Verify both events were triggered exactly once
    assert watcher.handler_registry.trigger_event.call_count == 2


@pytest.mark.asyncio
async def test_check_repo_updates_no_duplicate_events(watcher):
    """Test that events are not triggered for already processed commits/PRs"""
    # Mock the API responses
    test_commit = {
        "sha": "abc123",
        "commit": {"message": "Test commit", "author": {"name": "Test Author"}},
        "html_url": "https://github.com/test/repo/commit/abc123",
    }
    test_pr = {
        "number": 1,
        "title": "Test PR",
        "user": {"login": "test-user"},
        "html_url": "https://github.com/test/repo/pull/1",
    }

    # Mock the API calls
    watcher._get_new_commits = AsyncMock(return_value=[test_commit])
    watcher._get_updated_prs = AsyncMock(return_value=[test_pr])
    watcher._update_repo_state = AsyncMock()

    # Test data with existing commit and PR
    repo = {
        "repo_url": "https://github.com/test/repo",
        "last_commit_sha": "abc123",  # Same as new commit
        "last_pr_number": 1,  # Same as new PR
        "last_check": datetime.now(timezone.utc),
    }

    # Run the update check
    await watcher._check_repo_updates(repo)

    # Verify no events were triggered for already processed items
    watcher.handler_registry.trigger_event.assert_not_called()
