import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.handlers.immunefi_asset_event_handler import ImmunefiAssetEventHandler
from src.handlers.base import HandlerTrigger
from src.models.base import Asset, AssetType, Project
from src.services.telegram import TelegramService


@pytest.fixture
def mock_telegram_service():
    service = Mock(spec=TelegramService)
    service.send_message = AsyncMock()
    with patch("src.services.telegram.TelegramService.get_instance", return_value=service):
        yield service


@pytest.fixture
def handler(mock_telegram_service):
    return ImmunefiAssetEventHandler()


@pytest.fixture
def sample_asset():
    asset = Mock(spec=Asset)
    asset.source_url = "https://github.com/example/repo"
    asset.asset_type = AssetType.GITHUB_FILE
    return asset


@pytest.fixture
def sample_project():
    project = Mock(spec=Project)
    project.name = "Test Project"
    project.description = "Test Description"
    project.project_type = "bounty"
    project.extra_data = {"maxBounty": 100000, "ecosystem": ["Ethereum"], "productType": ["DeFi"]}
    return project


@pytest.mark.asyncio
async def test_new_asset_event(handler, sample_asset, sample_project, mock_telegram_service):
    """Test handling of new asset event"""
    # Set up the asset with a project relationship
    sample_asset.project = sample_project
    handler.trigger = HandlerTrigger.NEW_ASSET
    handler.context = {"asset": sample_asset}

    await handler.handle()

    # Verify notification was sent
    mock_telegram_service.send_message.assert_called_once()
    message = mock_telegram_service.send_message.call_args[0][0]

    # Check message content
    assert "New Asset Added" in message
    assert sample_asset.source_url in message
    assert sample_project.name in message
    assert "$100,000" in message
    assert "Ethereum" in message
    assert "DeFi" in message


@pytest.mark.asyncio
async def test_asset_update_event(handler, sample_asset, sample_project, mock_telegram_service):
    """Test handling of asset update event"""
    # Set up the asset with a project relationship
    sample_asset.project = sample_project
    handler.trigger = HandlerTrigger.ASSET_UPDATE
    handler.context = {"asset": sample_asset, "old_revision": "abc123", "new_revision": "def456"}

    await handler.handle()

    # Verify notification was sent
    mock_telegram_service.send_message.assert_called_once()
    message = mock_telegram_service.send_message.call_args[0][0]
    assert "Asset Updated" in message
    assert sample_asset.source_url in message
    assert "abc123 → def456" in message
    assert sample_project.name in message
    assert "$100,000" in message
    assert "Ethereum" in message
    assert "DeFi" in message


@pytest.mark.asyncio
async def test_asset_update_with_diff(handler, sample_asset, sample_project, mock_telegram_service):
    """Test handling of asset update event with diff info"""
    # Set up the asset with a project relationship
    sample_asset.project = sample_project
    handler.trigger = HandlerTrigger.ASSET_UPDATE
    handler.context = {
        "asset": sample_asset,
        "old_revision": "abc123",
        "new_revision": "def456",
        "old_path": "/tmp/old.txt",
        "new_path": "/tmp/new.txt",
    }

    await handler.handle()

    # Verify notification was sent with diff info
    mock_telegram_service.send_message.assert_called_once()
    message = mock_telegram_service.send_message.call_args[0][0]
    assert "Asset Updated" in message
    assert "File diff available" in message
    assert sample_project.name in message


@pytest.mark.asyncio
async def test_missing_context(handler, mock_telegram_service):
    """Test handling with missing context"""
    handler.context = {}

    result = await handler.handle()

    # Verify no notification was sent
    mock_telegram_service.send_message.assert_not_called()
    assert not result.success
    assert "No context provided" in result.data["error"]


@pytest.mark.asyncio
async def test_missing_asset(handler, sample_project, mock_telegram_service):
    """Test handling with missing asset"""
    handler.context = {"project": sample_project}

    result = await handler.handle()

    # Verify no notification was sent
    mock_telegram_service.send_message.assert_not_called()
    assert not result.success
    assert "No asset in context" in result.data["error"]


@pytest.mark.asyncio
async def test_missing_project(handler, sample_asset, mock_telegram_service):
    """Test handling with missing project"""
    sample_asset.project = None  # Ensure no project is associated
    handler.context = {"asset": sample_asset}

    result = await handler.handle()

    # Verify no notification was sent
    mock_telegram_service.send_message.assert_not_called()
    assert not result.success
    assert "No project associated" in result.data["error"]


def test_handler_triggers():
    """Test that handler listens for correct triggers"""
    triggers = ImmunefiAssetEventHandler.get_triggers()
    assert HandlerTrigger.ASSET_UPDATE in triggers
    assert HandlerTrigger.NEW_ASSET in triggers
    assert len(triggers) == 2  # Should handle both ASSET_UPDATE and NEW_ASSET
