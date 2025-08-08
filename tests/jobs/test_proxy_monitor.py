import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from src.jobs.proxy_monitor import ProxyMonitorJob
from src.models.base import Asset, AssetType
from src.handlers.base import HandlerTrigger


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.__enter__.return_value = session
    session.__exit__.return_value = None

    def add_mock(obj):
        # Simulate the session tracking the object
        pass

    def commit_mock():
        # Simulate the commit applying changes
        pass

    # Mock the session methods properly
    session.add = MagicMock(side_effect=add_mock)
    session.commit = MagicMock(side_effect=commit_mock)
    session.rollback = MagicMock()

    return session


@pytest.fixture
def proxy_monitor(mock_session):
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
    contract = Asset(
        identifier="https://etherscan.io/address/0x123",
        asset_type=AssetType.DEPLOYED_CONTRACT,
        extra_data={},  # Initialize with empty dict
        is_proxy=False,
        checked_for_proxy=False,
    )
    mock_session.query.return_value.filter.return_value.all.return_value = [contract]
    proxy_monitor.explorer.get_proxy_upgrade_events = AsyncMock(return_value=[])

    await proxy_monitor.start()

    # Verify contract was marked as checked and non-proxy
    assert contract.checked_for_proxy is True  # This should now work
    assert contract.is_proxy is False
    assert contract.extra_data == {}  # Non-proxies shouldn't have implementation history


@pytest.mark.asyncio
async def test_proxy_monitor_handles_upgrade(proxy_monitor, mock_session):
    """Test that proxy upgrades are properly handled"""
    old_impl = Asset(
        identifier="https://etherscan.io/address/0x789",
        asset_type=AssetType.DEPLOYED_CONTRACT,
        extra_data={"is_implementation": True},
    )
    proxy = Asset(
        identifier="https://etherscan.io/address/0x123",
        asset_type=AssetType.DEPLOYED_CONTRACT,
        extra_data={},  # Initialize with empty dict
        implementation=old_impl,
        project_id=1,
        is_proxy=True,
        checked_for_proxy=True,
    )
    mock_session.query.return_value.filter.return_value.all.return_value = [proxy]
    mock_session.query.return_value.filter.return_value.first.return_value = None

    # Mock explorer responses
    proxy_monitor.explorer.is_supported_explorer = Mock(return_value=(True, "etherscan"))
    proxy_monitor.explorer.EXPLORERS = {"etherscan": {"domain": "etherscan.io"}}
    proxy_monitor.explorer.get_proxy_upgrade_events = AsyncMock(
        return_value=[{"implementation": "0x456", "blockNumber": 1234, "timestamp": 1234567890}]
    )

    await proxy_monitor.start()

    # Verify implementation history was updated
    assert proxy.extra_data.get("implementation_history") is not None
    assert len(proxy.extra_data["implementation_history"]) == 1
    assert proxy.extra_data["implementation_history"][0]["address"] == "0x456"


@pytest.mark.asyncio
async def test_proxy_monitor_handles_first_implementation(proxy_monitor, mock_session):
    """Test that first implementation is handled without triggering upgrade event"""
    proxy = Asset(
        identifier="https://etherscan.io/address/0x123",
        asset_type=AssetType.DEPLOYED_CONTRACT,
        extra_data={},  # Initialize with empty dict
        implementation=None,
        project_id=1,
        is_proxy=False,
        checked_for_proxy=False,
    )
    mock_session.query.return_value.filter.return_value.all.return_value = [proxy]
    mock_session.query.return_value.filter.return_value.first.return_value = None

    # Mock explorer responses
    proxy_monitor.explorer.is_supported_explorer = Mock(return_value=(True, "etherscan"))
    proxy_monitor.explorer.EXPLORERS = {"etherscan": {"domain": "etherscan.io"}}
    proxy_monitor.explorer.get_proxy_upgrade_events = AsyncMock(
        return_value=[{"implementation": "0x456", "blockNumber": 1234, "timestamp": 1234567890}]
    )

    await proxy_monitor.start()

    # Verify implementation history was created
    assert proxy.extra_data.get("implementation_history") is not None
    assert len(proxy.extra_data["implementation_history"]) == 1
    assert proxy.extra_data["implementation_history"][0]["address"] == "0x456"


@pytest.mark.asyncio
async def test_proxy_monitor_handles_errors(proxy_monitor, mock_session):
    """Test that errors are properly handled"""
    contract = Asset(
        identifier="https://etherscan.io/address/0x123",
        asset_type=AssetType.DEPLOYED_CONTRACT,
        extra_data={},  # Initialize as empty dict
        is_proxy=False,
        checked_for_proxy=False,
    )
    mock_session.query.return_value.filter.return_value.all.return_value = [contract]
    proxy_monitor.explorer.get_proxy_upgrade_events = AsyncMock(side_effect=Exception("API Error"))

    # Run job
    await proxy_monitor.start()

    # Verify error was handled
    assert mock_session.rollback.called
    assert contract.checked_for_proxy is False
    assert contract.is_proxy is False
    assert "implementation_history" not in contract.extra_data
