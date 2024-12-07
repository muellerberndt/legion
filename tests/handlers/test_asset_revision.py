import pytest
from unittest.mock import Mock, patch
from src.handlers.asset_revision import AssetRevisionHandler
from src.handlers.base import HandlerTrigger
from src.models.base import Asset, AssetType
from src.services.notification_service import NotificationService


class MockNotificationService(NotificationService):
    """Mock notification service for testing"""

    def __init__(self):
        self.messages = []

    async def send_message(self, message: str) -> None:
        """Implement abstract method"""
        self.messages.append(message)


@pytest.fixture
def mock_notification_service():
    """Fixture to provide mock notification service"""
    service = MockNotificationService()
    with patch("src.handlers.asset_revision.NotificationService.get_instance", return_value=service):
        yield service


@pytest.fixture
def mock_asset():
    """Fixture to provide mock asset"""
    asset = Mock(spec=Asset)
    asset.id = "test-asset-1"
    asset.asset_type = AssetType.GITHUB_FILE
    asset.extra_data = {}
    return asset


@pytest.fixture
def mock_diff_result():
    """Fixture to provide mock diff result"""

    class MockDiffResult:
        def __init__(self):
            self.has_changes = True
            self.added_lines = [(1, "new line")]
            self.removed_lines = [(2, "old line")]
            self.modified_lines = [(3, 4, "old", "new")]

        def to_dict(self):
            return {"added": self.added_lines, "removed": self.removed_lines, "modified": self.modified_lines}

    return MockDiffResult()


@pytest.mark.asyncio
async def test_asset_update_with_diff(mock_asset, mock_diff_result, mock_notification_service):
    """Test handling asset update with file diff"""
    handler = AssetRevisionHandler()

    # Set up context
    handler.context = {
        "asset": mock_asset,
        "old_revision": "abc123",
        "new_revision": "def456",
        "old_path": "/tmp/old.sol",
        "new_path": "/tmp/new.sol",
    }

    # Mock compute_file_diff
    with patch("src.handlers.asset_revision.compute_file_diff", return_value=mock_diff_result):
        await handler.handle()

    # Verify diff was stored
    assert mock_asset.extra_data.get("diff") == mock_diff_result.to_dict()

    # Verify notification was sent
    assert len(mock_notification_service.messages) == 1
    assert "Changes detected in test-asset-1" in mock_notification_service.messages[0]
    assert "1 lines added" in mock_notification_service.messages[0]
    assert "1 lines removed" in mock_notification_service.messages[0]
    assert "1 lines modified" in mock_notification_service.messages[0]


@pytest.mark.asyncio
async def test_asset_update_no_changes(mock_asset, mock_notification_service):
    """Test handling asset update with no changes"""
    handler = AssetRevisionHandler()

    # Set up context
    handler.context = {
        "asset": mock_asset,
        "old_revision": "abc123",
        "new_revision": "def456",
        "old_path": "/tmp/old.sol",
        "new_path": "/tmp/new.sol",
    }

    # Mock diff result with no changes
    no_changes_diff = Mock()
    no_changes_diff.has_changes = False

    with patch("src.handlers.asset_revision.compute_file_diff", return_value=no_changes_diff):
        await handler.handle()

    # Verify no diff was stored
    assert "diff" not in mock_asset.extra_data

    # Verify notification about no changes
    assert len(mock_notification_service.messages) == 1
    assert "No changes detected" in mock_notification_service.messages[0]


@pytest.mark.asyncio
async def test_asset_removal(mock_asset, mock_notification_service):
    """Test handling asset removal"""
    handler = AssetRevisionHandler()

    # Set up context for removal
    handler.context = {"asset": mock_asset, "removed": True}

    await handler.handle()

    # Verify removal notification
    assert len(mock_notification_service.messages) == 1
    assert f"Asset {mock_asset.id} removed" in mock_notification_service.messages[0]


@pytest.mark.asyncio
async def test_missing_context(mock_notification_service):
    """Test handling missing context"""
    handler = AssetRevisionHandler()
    await handler.handle()  # Should not raise exception
    assert len(mock_notification_service.messages) == 0


@pytest.mark.asyncio
async def test_missing_asset(mock_notification_service):
    """Test handling missing asset in context"""
    handler = AssetRevisionHandler()
    handler.context = {"some": "data"}
    await handler.handle()  # Should not raise exception
    assert len(mock_notification_service.messages) == 0


@pytest.mark.asyncio
async def test_diff_computation_error(mock_asset, mock_notification_service):
    """Test handling error during diff computation"""
    handler = AssetRevisionHandler()

    # Set up context
    handler.context = {
        "asset": mock_asset,
        "old_revision": "abc123",
        "new_revision": "def456",
        "old_path": "/tmp/old.sol",
        "new_path": "/tmp/new.sol",
    }

    # Mock compute_file_diff to raise exception
    with patch("src.handlers.asset_revision.compute_file_diff", side_effect=Exception("Test error")):
        await handler.handle()

    # Verify error notification
    assert len(mock_notification_service.messages) == 1
    assert "Failed to compute diff" in mock_notification_service.messages[0]


@pytest.mark.asyncio
async def test_get_triggers():
    """Test handler triggers"""
    triggers = AssetRevisionHandler.get_triggers()
    assert HandlerTrigger.ASSET_UPDATE in triggers
