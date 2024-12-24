import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timezone, timedelta
from src.jobs.github_monitor import GithubMonitorJob
from src.models.github import GitHubRepoState
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def mock_session():
    """Mock database session"""
    session = AsyncMock(spec=AsyncSession)

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

    # Set up execute to return repo results
    session.execute = AsyncMock(return_value=mock_repo_result)

    # Mock get method for GitHubRepoState
    async def mock_get(model_class, repo_url):
        if model_class == GitHubRepoState:
            return None  # Simulate no existing state
        return None

    session.get = AsyncMock(side_effect=mock_get)

    # Mock add (not async) and commit (async) methods
    session.add = Mock()  # Regular Mock since add is not async
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    return session


class AsyncSessionFactory:
    """Factory for async sessions that returns an async context manager"""

    def __init__(self, session):
        self.session = session

    async def __call__(self):
        return AsyncSessionContextManager(self.session)


class AsyncSessionContextManager:
    """Async context manager for database session"""

    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self.session.rollback()
        await self.session.commit()


@pytest.fixture
async def github_monitor(mock_session):
    """Create GitHub monitor instance with mocked dependencies"""
    job = GithubMonitorJob()

    # Set up the session factory
    job.get_async_session = AsyncSessionFactory(mock_session)

    # Set up handler registry
    job.handler_registry = AsyncMock()
    job.handler_registry.trigger_event = AsyncMock()

    # Mock GitHub API session
    job.session = AsyncMock()

    # Mock GitHub API responses
    commit_response = AsyncMock()
    commit_response.status = 200
    commit_response.json = AsyncMock(return_value=[{"sha": "new-sha", "commit": {"message": "test commit"}}])

    pr_response = AsyncMock()
    pr_response.status = 200
    pr_response.json = AsyncMock(return_value=[{"number": 2, "updated_at": datetime.now(timezone.utc).isoformat()}])

    job.session.get = AsyncMock(side_effect=[commit_response, pr_response])

    return job
