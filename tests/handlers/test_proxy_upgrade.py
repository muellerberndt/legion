import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.handlers.proxy_upgrade import ProxyUpgradeHandler
from src.handlers.base import HandlerTrigger, HandlerResult
from src.models.base import Asset, Project
from src.services.telegram import TelegramService


@pytest.fixture
def mock_telegram():
    with patch.object(TelegramService, "get_instance") as mock:
        telegram = Mock()
        telegram.send_message = AsyncMock()
        mock.return_value = telegram
        yield telegram


@pytest.fixture
def handler(mock_telegram):
    handler = ProxyUpgradeHandler()
    handler.logger = Mock()
    return handler


@pytest.fixture
def proxy_asset():
    project = Project(name="Test Project", project_type="defi")
    proxy = Asset(identifier="https://etherscan.io/address/0x123", project=project)
    return proxy


@pytest.fixture
def implementation_assets():
    old_impl = Asset(
        identifier="https://etherscan.io/address/0x456",
        get_code=Mock(return_value="contract OldImpl { function value() public returns (uint) { return 1; } }"),
    )
    new_impl = Asset(
        identifier="https://etherscan.io/address/0x789",
        get_code=Mock(return_value="contract NewImpl { function value() public returns (uint) { return 2; } }"),
    )
    return old_impl, new_impl


@pytest.mark.asyncio
async def test_handler_no_context(handler):
    """Test handler with no context"""
    result = await handler.handle()
    assert not result.success
    assert "No context provided" in result.data["error"]


@pytest.mark.asyncio
async def test_handler_missing_data(handler, proxy_asset):
    """Test handler with missing context data"""
    handler.set_context({"proxy": proxy_asset})  # Missing implementation and event
    result = await handler.handle()
    assert not result.success
    assert "Missing required context data" in result.data["error"]


@pytest.mark.asyncio
async def test_handler_no_security_impact(handler, proxy_asset, implementation_assets, mock_telegram):
    """Test handler when no security impact is detected"""
    old_impl, new_impl = implementation_assets
    event = {"blockNumber": 1234, "timestamp": 1234567890}

    handler.set_context({"proxy": proxy_asset, "old_implementation": old_impl, "new_implementation": new_impl, "event": event})

    # Mock LLM response indicating no security impact
    with patch("src.handlers.proxy_upgrade.chat_completion", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = "Minor update to return value. Security Impact: No"

        result = await handler.handle()

        assert result.success
        assert result.data["message"] == "No security impact detected"
        assert not mock_telegram.send_message.called


@pytest.mark.asyncio
async def test_handler_with_security_impact(handler, proxy_asset, implementation_assets, mock_telegram):
    """Test handler when security impact is detected"""
    old_impl, new_impl = implementation_assets
    event = {"blockNumber": 1234, "timestamp": 1234567890}

    handler.set_context({"proxy": proxy_asset, "old_implementation": old_impl, "new_implementation": new_impl, "event": event})

    # Mock LLM response indicating security impact
    with patch("src.handlers.proxy_upgrade.chat_completion", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = "Critical change to access control. Security Impact: Yes"

        result = await handler.handle()

        assert result.success
        assert mock_telegram.send_message.called

        # Verify notification content
        call_args = mock_telegram.send_message.call_args[0][0]
        assert "Security-Relevant Proxy Upgrade" in call_args
        assert proxy_asset.identifier in call_args
        assert new_impl.identifier in call_args
        assert "Critical change to access control" in call_args
        assert "Test Project" in call_args


@pytest.mark.asyncio
async def test_handler_missing_implementation_code(handler, proxy_asset, implementation_assets, mock_telegram):
    """Test handler when implementation code cannot be retrieved"""
    old_impl, new_impl = implementation_assets
    new_impl.get_code = Mock(return_value=None)  # Simulate failed code
