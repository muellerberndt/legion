import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from src.jobs.proxy_monitor import ProxyMonitorJob
from src.models.base import Asset, AssetType
from src.handlers.base import HandlerTrigger
from src.services.telegram import TelegramService


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.__enter__.return_value = session
    session.__exit__.return_value = None

    # Mock the session methods properly
    session.add = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()

    return session


@pytest.fixture
def mock_telegram():
    with patch.object(TelegramService, "get_instance") as mock:
        telegram = Mock()
        telegram.send_message = AsyncMock()
        mock.return_value = telegram
        yield telegram


@pytest.fixture
def proxy_monitor(mock_session, mock_telegram):
    with patch("src.jobs.proxy_monitor.fetch_verified_sources", new_callable=AsyncMock):
        job = ProxyMonitorJob()
        job.get_session = Mock(return_value=mock_session)
        job.explorer = Mock()
        job.handler_registry = Mock()
        job.logger = Mock()
        yield job


@pytest.mark.asyncio
async def test_proxy_monitor_marks_non_proxy(proxy_monitor, mock_session):
    """Test that contracts without upgrade events are marked as non-proxies"""
    # Setup test contract
    contract = Asset(identifier="https://etherscan.io/address/0x123", asset_type=AssetType.DEPLOYED_CONTRACT, extra_data={})
    mock_session.query.return_value.filter.return_value.all.return_value = [contract]
    proxy_monitor.explorer.get_proxy_upgrade_events = AsyncMock(return_value=[])

    # Add debug logging
    proxy_monitor.logger.debug = Mock()

    # Run job
    await proxy_monitor.start()

    # Print debug info
    print(f"Contract extra_data after: {contract.extra_data}")
    print(f"Session add called: {mock_session.add.call_args_list}")
    print(f"Session commit called: {mock_session.commit.call_args_list}")

    # Verify contract was marked as non-proxy
    assert contract.extra_data is not None, "extra_data should not be None"
    assert (
        "is_not_proxy" in contract.extra_data
    ), f"is_not_proxy should be in extra_data. Current extra_data: {contract.extra_data}"
    assert contract.extra_data["is_not_proxy"]
    assert mock_session.add.call_args == call(contract)
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_proxy_monitor_handles_upgrade(proxy_monitor, mock_session):
    """Test that proxy upgrades are properly handled"""
    # Setup test contract with an existing implementation
    old_impl = Asset(
        identifier="https://etherscan.io/address/0x789",
        asset_type=AssetType.DEPLOYED_CONTRACT,
        extra_data={"is_implementation": True},
    )
    proxy = Asset(
        identifier="https://etherscan.io/address/0x123",
        asset_type=AssetType.DEPLOYED_CONTRACT,
        extra_data={},
        implementation=old_impl,  # Set existing implementation
        project_id=1,  # Add project_id for path construction
    )
    mock_session.query.return_value.filter.return_value.all.return_value = [proxy]
    mock_session.query.return_value.filter.return_value.first.return_value = None  # New implementation not found

    # Mock explorer responses
    proxy_monitor.explorer.is_supported_explorer = Mock(return_value=(True, "etherscan"))
    proxy_monitor.explorer.EXPLORERS = {"etherscan": {"domain": "etherscan.io"}}
    proxy_monitor.explorer.get_proxy_upgrade_events = AsyncMock(
        return_value=[{"implementation": "0x456", "blockNumber": 1234, "timestamp": 1234567890}]
    )

    # Run job
    await proxy_monitor.start()

    # Verify implementation was recorded
    assert proxy.extra_data is not None, "extra_data should not be None"
    assert "implementation_history" in proxy.extra_data, f"implementation_history not found in {proxy.extra_data}"
    assert len(proxy.extra_data["implementation_history"]) == 1
    assert proxy.extra_data["implementation_history"][0]["address"] == "0x456"

    # Verify event was triggered
    proxy_monitor.handler_registry.trigger_event.assert_called_once()
    call_args = proxy_monitor.handler_registry.trigger_event.call_args
    assert call_args[0][0] == HandlerTrigger.CONTRACT_UPGRADED
    assert call_args[0][1]["proxy"] == proxy
    assert call_args[0][1]["old_implementation"] == old_impl


@pytest.mark.asyncio
async def test_proxy_monitor_handles_first_implementation(proxy_monitor, mock_session):
    """Test that first implementation is handled without triggering upgrade event"""
    # Setup test contract without implementation
    proxy = Asset(
        identifier="https://etherscan.io/address/0x123",
        asset_type=AssetType.DEPLOYED_CONTRACT,
        extra_data={},
        implementation=None,  # No existing implementation
        project_id=1,  # Add project_id for path construction
    )
    mock_session.query.return_value.filter.return_value.all.return_value = [proxy]
    mock_session.query.return_value.filter.return_value.first.return_value = None

    # Mock explorer responses
    proxy_monitor.explorer.is_supported_explorer = Mock(return_value=(True, "etherscan"))
    proxy_monitor.explorer.EXPLORERS = {"etherscan": {"domain": "etherscan.io"}}
    proxy_monitor.explorer.get_proxy_upgrade_events = AsyncMock(
        return_value=[{"implementation": "0x456", "blockNumber": 1234, "timestamp": 1234567890}]
    )

    # Run job
    await proxy_monitor.start()

    # Verify implementation was recorded
    assert proxy.extra_data is not None, "extra_data should not be None"
    assert "implementation_history" in proxy.extra_data, f"implementation_history not found in {proxy.extra_data}"
    assert len(proxy.extra_data["implementation_history"]) == 1
    assert proxy.extra_data["implementation_history"][0]["address"] == "0x456"

    # Verify no event was triggered
    proxy_monitor.handler_registry.trigger_event.assert_not_called()


@pytest.mark.asyncio
async def test_proxy_monitor_handles_errors(proxy_monitor, mock_session):
    """Test that errors are properly handled"""
    # Setup test contract
    contract = Asset(identifier="https://etherscan.io/address/0x123", asset_type=AssetType.DEPLOYED_CONTRACT, extra_data={})
    mock_session.query.return_value.filter.return_value.all.return_value = [contract]
    proxy_monitor.explorer.get_proxy_upgrade_events = AsyncMock(side_effect=Exception("API Error"))

    # Run job
    await proxy_monitor.start()

    # Verify error was handled
    assert mock_session.rollback.called
    # Contract should not be marked as non-proxy on error
    assert "is_not_proxy" not in contract.extra_data
