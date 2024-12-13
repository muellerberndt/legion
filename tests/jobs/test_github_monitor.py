import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone, timedelta
from src.jobs.github_monitor import GithubMonitorJob
from src.handlers.base import HandlerTrigger
from src.util.logging import Logger
from src.models.github import GitHubRepoState


class MockDBSession:
    def __init__(self, mock_session):
        self.mock_session = mock_session

    async def __call__(self, *args, **kwargs):
        return self.mock_session


class AsyncSessionContextManager:
    """Custom async context manager for database session"""

    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
async def mock_session():
    """Mock database session"""
    session = AsyncMock()

    # Set up the chain of mock calls for repo queries
    session.scalar = AsyncMock(return_value=5)  # 5 bounty projects

    # Mock direct repos query
    mock_direct_result = AsyncMock()
    mock_direct_result.all.return_value = [
        Mock(source_url="https://github.com/owner/repo1", asset_type="github_repo"),
        Mock(source_url="https://github.com/owner/repo2", asset_type="github_file"),
    ]

    # Mock repo state query
    mock_repo_result = AsyncMock()
    mock_repo_result.all.return_value = [
        Mock(
            repo_url="https://github.com/owner/repo1",
            last_commit_sha="old-sha",
            last_pr_number=1,
            last_check=datetime.now(timezone.utc) - timedelta(hours=2),
        )
    ]

    # Set up execute to return different results based on query
    async def mock_execute(*args, **kwargs):
        if "SELECT DISTINCT a.source_url" in str(args[0]):
            return mock_direct_result
        return mock_repo_result

    session.execute = AsyncMock(side_effect=mock_execute)

    return session


@pytest.fixture
def mock_http_session():
    """Mock aiohttp ClientSession"""
    session = AsyncMock()
    session.get = AsyncMock()
    return session


@pytest.fixture
async def job(mock_session, mock_http_session):
    """Create a GithubMonitorJob instance with mocked sessions"""
    job = GithubMonitorJob()
    job.session = mock_http_session
    job.handler_registry.trigger_event = AsyncMock()
    return job


@pytest.mark.asyncio
async def test_initialize(job):
    """Test job initialization"""
    await job.initialize()
    assert job.session is not None


@pytest.mark.asyncio
async def test_check_repo_updates_new_commit(job, mock_http_session):
    """Test checking for new commits"""
    # Mock commit response
    commit_response = AsyncMock()
    commit_response.status = 200
    commit_response.json = AsyncMock(return_value=[{"sha": "new-sha", "commit": {"message": "New commit"}}])

    # Mock PR response
    pr_response = AsyncMock()
    pr_response.status = 200
    pr_response.json = AsyncMock(return_value=[])

    # Set up session responses
    mock_http_session.get.side_effect = [commit_response, pr_response]

    # Test data
    repo = {
        "repo_url": "https://github.com/owner/repo",
        "last_commit_sha": "old-sha",
        "last_pr_number": 1,
        "last_check": datetime.now(timezone.utc) - timedelta(hours=2),
    }

    # Run the update check
    await job._check_repo_updates(repo)

    # Verify event was triggered for new commit
    job.handler_registry.trigger_event.assert_called_with(
        HandlerTrigger.GITHUB_PUSH,
        {"payload": {"repo_url": repo["repo_url"], "commit": {"sha": "new-sha", "commit": {"message": "New commit"}}}},
    )


@pytest.mark.asyncio
async def test_check_repo_updates_new_pr(job, mock_http_session):
    """Test checking for new pull requests"""
    # Mock commit response
    commit_response = AsyncMock()
    commit_response.status = 200
    commit_response.json = AsyncMock(return_value=[])

    # Mock PR response
    pr_response = AsyncMock()
    pr_response.status = 200
    pr_response.json = AsyncMock(
        return_value=[{"number": 2, "title": "New PR", "updated_at": datetime.now(timezone.utc).isoformat()}]
    )

    # Set up session responses
    mock_http_session.get.side_effect = [commit_response, pr_response]

    # Test data
    repo = {
        "repo_url": "https://github.com/owner/repo",
        "last_commit_sha": "old-sha",
        "last_pr_number": 1,
        "last_check": datetime.now(timezone.utc) - timedelta(hours=2),
    }

    # Run the update check
    await job._check_repo_updates(repo)

    # Verify event was triggered for new PR
    job.handler_registry.trigger_event.assert_called_with(
        HandlerTrigger.GITHUB_PR,
        {
            "payload": {
                "repo_url": repo["repo_url"],
                "pull_request": {"number": 2, "title": "New PR", "updated_at": pr_response.json.return_value[0]["updated_at"]},
            }
        },
    )


@pytest.mark.asyncio
async def test_start_and_stop(job):
    """Test starting and stopping the job"""
    # Start the job in the background
    task = asyncio.create_task(job.start())

    # Let it run for a moment
    await asyncio.sleep(0.1)

    # Stop the job
    await job.stop()

    # Wait for the job to finish
    await task

    assert job.status.value == "completed"
    assert job.result is not None
    assert job.result.success is True


@pytest.mark.asyncio
async def test_error_handling(job, mock_http_session):
    """Test error handling during repository checks"""
    # Mock an error response
    error_response = AsyncMock()
    error_response.status = 403
    error_response.text = AsyncMock(return_value="API rate limit exceeded")

    mock_http_session.get.return_value = error_response

    # Test data
    repo = {
        "repo_url": "https://github.com/owner/repo",
        "last_commit_sha": None,
        "last_pr_number": None,
        "last_check": None,
    }

    # Run the update check
    await job._check_repo_updates(repo)

    # Verify no events were triggered
    job.handler_registry.trigger_event.assert_not_called()


@pytest.mark.asyncio
async def test_parse_repo_url():
    """Test repository URL parsing"""
    job = GithubMonitorJob()

    # Test valid URL
    owner, repo = job._parse_repo_url("https://github.com/owner/repo")
    assert owner == "owner"
    assert repo == "repo"

    # Test invalid URL
    owner, repo = job._parse_repo_url("https://not-github.com/owner/repo")
    assert owner is None
    assert repo is None

    # Test malformed URL
    owner, repo = job._parse_repo_url("not-a-url")
    assert owner is None
    assert repo is None
