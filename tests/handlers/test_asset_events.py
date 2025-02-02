import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.handlers.asset_events import AssetEventHandler
from src.handlers.base import HandlerTrigger, HandlerResult
from src.models.base import Asset, Project, AssetType
from src.services.telegram import TelegramService
import io
from datetime import datetime


@pytest.fixture
def mock_telegram():
    """Mock telegram service"""
    mock = Mock(spec=TelegramService)
    mock.send_message = AsyncMock()
    mock.send_document = AsyncMock()
    return mock


@pytest.fixture
def handler(mock_telegram):
    """Create handler with mocked telegram"""
    with patch("src.handlers.asset_events.TelegramService") as mock_telegram_class:
        mock_telegram_class.get_instance.return_value = mock_telegram
        handler = AssetEventHandler()
        handler.telegram = mock_telegram
        return handler


@pytest.fixture
def sample_project():
    """Create a sample project"""
    return Project(id=1, name="Test Project", project_type="test", project_source="immunefi")


@pytest.fixture
def sample_asset(sample_project):
    """Create a sample asset"""
    return Asset(
        id=1,
        identifier="test-asset",
        project=sample_project,
        asset_type=AssetType.DEPLOYED_CONTRACT,
        source_url="https://etherscan.io/address/0x123",
        local_path="/tmp/test/contract",
        extra_data={"revision": 1},
    )


@pytest.mark.asyncio
async def test_handle_missing_context(handler):
    """Test handling with missing context"""
    handler.context = None
    handler.trigger = HandlerTrigger.ASSET_UPDATE

    result = await handler.handle()

    assert isinstance(result, HandlerResult)
    assert not result.success
    assert result.data["error"] == "Missing context or trigger"


@pytest.mark.asyncio
async def test_handle_asset_update_with_diff(handler, sample_asset, mock_telegram):
    """Test handling asset update with code changes"""
    old_code = "contract Old { uint256 value; }"
    new_code = "contract New { uint256 value; function get() returns (uint256) { return value; } }"

    handler.context = {
        "asset": sample_asset,
        "old_path": "/tmp/old",
        "new_path": "/tmp/new",
        "old_revision": 1,
        "new_revision": 2,
        "old_code": old_code,
        "new_code": new_code,
    }
    handler.trigger = HandlerTrigger.ASSET_UPDATE

    result = await handler.handle()

    assert isinstance(result, HandlerResult)
    assert result.success
    assert result.data["event"] == "asset_updated"
    assert result.data["project"] == "Test Project"
    assert result.data["old_revision"] == 1
    assert result.data["new_revision"] == 2

    # Verify message was sent
    mock_telegram.send_message.assert_called_once()
    message = mock_telegram.send_message.call_args[0][0]
    assert "📝 Asset Updated" in message
    assert "Test Project" in message
    assert "Revision: 1 → 2" in message

    # Verify diff was sent
    mock_telegram.send_document.assert_called_once()
    sent_doc = mock_telegram.send_document.call_args[0][0]
    assert isinstance(sent_doc, io.BytesIO)
    assert sent_doc.name.endswith(".html")


@pytest.mark.asyncio
async def test_handle_asset_update_no_changes(handler, sample_asset, mock_telegram):
    """Test handling asset update with no code changes"""
    handler.context = {
        "asset": sample_asset,
        "old_path": "/tmp/old",
        "new_path": "/tmp/new",
        "old_revision": 1,
        "new_revision": 1,  # Same revision
    }
    handler.trigger = HandlerTrigger.ASSET_UPDATE

    result = await handler.handle()

    assert isinstance(result, HandlerResult)
    assert result.success
    assert result.data["event"] == "asset_updated"

    # Verify message was sent
    mock_telegram.send_message.assert_called_once()
    message = mock_telegram.send_message.call_args[0][0]
    assert "📝 Asset Updated" in message
    assert "Test Project" in message
    assert "Revision:" not in message  # No revision change mentioned


@pytest.mark.asyncio
async def test_handle_asset_update_github_repo(handler, sample_asset, mock_telegram):
    """Test handling asset update for GitHub repo"""
    sample_asset.asset_type = AssetType.GITHUB_REPO

    handler.context = {"asset": sample_asset, "old_revision": "abc123", "new_revision": "def456"}
    handler.trigger = HandlerTrigger.ASSET_UPDATE

    result = await handler.handle()

    assert isinstance(result, HandlerResult)
    assert result.success
    assert result.data["event"] == "asset_updated"

    # Verify message was sent
    mock_telegram.send_message.assert_called_once()
    message = mock_telegram.send_message.call_args[0][0]
    assert "📝 Asset Updated" in message
    assert "Test Project" in message
    assert "ℹ️ No diff available for repository updates" in message
