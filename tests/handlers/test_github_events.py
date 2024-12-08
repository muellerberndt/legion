import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.handlers.github_events import GitHubEventHandler
from src.handlers.base import HandlerTrigger
from src.jobs.manager import JobManager


@pytest.fixture
def mock_job_manager():
    """Mock job manager"""
    return Mock(spec=JobManager)


@pytest.fixture
def event_handler(mock_job_manager):
    """Create event handler with mocked dependencies"""
    handler = GitHubEventHandler()
    with patch("src.handlers.github_events.JobManager", return_value=mock_job_manager):
        yield handler


@pytest.mark.asyncio
async def test_handler_process_pr(event_handler, mock_job_manager):
    """Test processing a pull request event"""
    # Setup
    event_handler.set_context(
        context={
            "payload": {
                "pull_request": {
                    "title": "Test PR",
                    "user": {"login": "test-user"},
                    "body": "Test description",
                    "html_url": "https://github.com/test/repo/pull/1",
                    "changed_files": 2,
                    "additions": 10,
                    "deletions": 5,
                },
                "repo_url": "https://github.com/test/repo",
            }
        },
        trigger=HandlerTrigger.GITHUB_PR,
    )

    mock_job_manager.submit_job = AsyncMock()

    # Execute
    await event_handler.handle()

    # Verify
    mock_job_manager.submit_job.assert_called_once()
    job = mock_job_manager.submit_job.call_args[0][0]
    assert job.event_type == "pull_request"
    assert job.payload == event_handler.context["payload"]


@pytest.mark.asyncio
async def test_handler_process_push(event_handler, mock_job_manager):
    """Test processing a push event"""
    # Setup
    event_handler.set_context(
        context={
            "payload": {
                "commit": {
                    "commit": {"message": "Test commit", "author": {"name": "test-user"}},
                    "html_url": "https://github.com/test/repo/commit/123",
                },
                "repo_url": "https://github.com/test/repo",
            }
        },
        trigger=HandlerTrigger.GITHUB_PUSH,
    )

    mock_job_manager.submit_job = AsyncMock()

    # Execute
    await event_handler.handle()

    # Verify
    mock_job_manager.submit_job.assert_called_once()
    job = mock_job_manager.submit_job.call_args[0][0]
    assert job.event_type == "push"
    assert job.payload == event_handler.context["payload"]


@pytest.mark.asyncio
async def test_handler_no_context(event_handler, mock_job_manager):
    """Test handling with no context"""
    # Setup
    event_handler.set_context(context=None, trigger=HandlerTrigger.GITHUB_PR)

    # Execute
    await event_handler.handle()

    # Verify
    mock_job_manager.submit_job.assert_not_called()


@pytest.mark.asyncio
async def test_handler_no_payload(event_handler, mock_job_manager):
    """Test handling with no payload"""
    # Setup
    event_handler.set_context(context={}, trigger=HandlerTrigger.GITHUB_PR)

    # Execute
    await event_handler.handle()

    # Verify
    mock_job_manager.submit_job.assert_not_called()


@pytest.mark.asyncio
async def test_handler_invalid_trigger(event_handler, mock_job_manager):
    """Test handling with invalid trigger"""
    # Setup
    event_handler.set_context(
        context={"payload": {"test": "data"}}, trigger=HandlerTrigger.NEW_PROJECT  # Using a different valid trigger
    )

    # Execute
    await event_handler.handle()

    # Verify
    mock_job_manager.submit_job.assert_not_called()


def test_handler_triggers():
    """Test handler trigger registration"""
    # Execute
    triggers = GitHubEventHandler.get_triggers()

    # Verify
    assert HandlerTrigger.GITHUB_PR in triggers
    assert HandlerTrigger.GITHUB_PUSH in triggers
    assert len(triggers) == 2
