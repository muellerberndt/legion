import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.handlers.project_events import ProjectEventHandler
from src.handlers.base import HandlerTrigger
from src.models.base import Project


from src.services.db_notification_service import DatabaseNotificationService


@pytest.fixture
def mock_notification_service():
    """Mock notification service"""
    mock = Mock(spec=DatabaseNotificationService)
    mock.send_message = AsyncMock()
    return mock


@pytest.fixture
def handler(mock_notification_service):
    with patch(
        "src.handlers.project_events.DatabaseNotificationService.get_instance", return_value=mock_notification_service
    ) as mock_get_instance:
        handler = ProjectEventHandler()
        handler.notification_service = mock_notification_service
        return handler


@pytest.fixture
def sample_project():
    project = Mock(spec=Project)
    project.name = "Test Project"
    project.description = "Test Description"
    project.project_type = "bounty"
    project.extra_data = {"maxBounty": "100000", "ecosystem": [], "language": []}
    project.assets = []
    return project


@pytest.mark.asyncio
async def test_new_project_event(handler, sample_project, mock_notification_service):
    """Test handling of new project event"""
    handler.context = {"project": sample_project}
    await handler.handle()

    # Verify notification was sent
    mock_notification_service.send_message.assert_called_once()
    message = mock_notification_service.send_message.call_args[0][0]
    assert "New Project Added" in message
    assert sample_project.name in message
    assert sample_project.project_type in message


@pytest.mark.asyncio
async def test_project_update_event(handler, sample_project, mock_notification_service):
    """Test handling of project update event"""
    new_project = Mock(spec=Project)
    new_project.name = "Test Project"
    new_project.description = "Updated Description"
    new_project.project_type = "bounty"
    new_project.extra_data = {"maxBounty": "200000"}
    new_project.assets = []

    handler.context = {"project": new_project, "old_project": sample_project}

    await handler.handle()

    # Verify notification was sent
    mock_notification_service.send_message.assert_called_once()
    message = mock_notification_service.send_message.call_args[0][0]
    assert "Project Updated" in message
    assert new_project.name in message
    assert "maxBounty: 100000 → 200000" in message


@pytest.mark.asyncio
async def test_project_removal_event(handler, sample_project, mock_notification_service):
    """Test handling of project removal event"""
    handler.context = {"project": sample_project, "removed": True}

    await handler.handle()

    # Verify notification was sent
    mock_notification_service.send_message.assert_called_once()
    message = mock_notification_service.send_message.call_args[0][0]
    assert "Project Removed" in message
    assert sample_project.name in message


@pytest.mark.asyncio
async def test_no_changes_update(handler, sample_project, mock_notification_service):
    """Test update event with no actual changes"""
    handler.context = {"project": sample_project, "old_project": sample_project}  # Same project, no changes

    await handler.handle()

    # Verify no notification was sent (no changes detected)
    mock_notification_service.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_missing_context(handler, mock_notification_service):
    """Test handling with missing context"""
    handler.context = {}

    await handler.handle()

    # Verify no notification was sent
    mock_notification_service.send_message.assert_not_called()


def test_handler_triggers():
    """Test that handler listens for correct triggers"""
    triggers = ProjectEventHandler.get_triggers()
    assert HandlerTrigger.NEW_PROJECT in triggers
    assert HandlerTrigger.PROJECT_UPDATE in triggers
    assert HandlerTrigger.PROJECT_REMOVE in triggers
