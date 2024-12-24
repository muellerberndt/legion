import pytest
from unittest.mock import MagicMock, AsyncMock
from src.handlers.base import HandlerTrigger
from extensions.examples.proxy_implementation_upgrade_handler import ProxyImplementationUpgradeHandler


@pytest.fixture
def handler():
    """Create a handler instance with mocked dependencies"""
    handler = ProxyImplementationUpgradeHandler()
    handler.telegram = MagicMock()
    handler.telegram.send_message = AsyncMock()  # Make it an async mock
    return handler


@pytest.fixture
def proxy_upgrade_event():
    """Sample proxy upgrade event data"""
    return {
        "source": "ethereum",
        "transaction_hash": "0x123...",
        "logs": [
            {
                "address": "0x1234567890123456789012345678901234567890",
                "topics": [
                    "0xbc7cd75a20ee27fd9adebab32041f755214dbc6bffa90cc0225b39da2e5c2d3b",
                    "0x0000000000000000000000009876543210987654321098765432109876543210",
                ],
            }
        ],
    }


@pytest.mark.asyncio
async def test_get_triggers():
    """Test that handler registers for blockchain events"""
    triggers = ProxyImplementationUpgradeHandler.get_triggers()
    assert HandlerTrigger.BLOCKCHAIN_EVENT in triggers


@pytest.mark.asyncio
async def test_is_contract_in_scope(handler):
    """Test contract scope checking"""
    # Mock the database session and query result
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [("1",)]  # Simulate finding one match
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Mock the async context manager
    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_session
    handler.get_async_session = MagicMock(return_value=mock_context)

    # Test with an in-scope contract
    result = await handler.is_contract_in_scope("0x1234567890123456789012345678901234567890")
    assert result is True

    # Verify query was built correctly
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_handle_upgrade_in_scope(handler, proxy_upgrade_event):
    """Test handling of an in-scope proxy upgrade event"""
    # Mock is_contract_in_scope to return True
    handler.is_contract_in_scope = AsyncMock(return_value=True)

    # Set up the context with both payload and source
    handler.context = {"source": proxy_upgrade_event["source"], "payload": proxy_upgrade_event}

    # Handle the event
    result = await handler.handle()

    # Verify success
    assert result.success is True
    assert result.data["found_upgrade"] is True
    assert result.data["in_scope"] is True

    # Verify contract addresses were extracted correctly
    assert result.data["contract_address"] == "0x1234567890123456789012345678901234567890"
    assert result.data["implementation_address"] == "0x9876543210987654321098765432109876543210"

    # Verify Telegram notification was sent with correct format
    handler.telegram.send_message.assert_called_once()
    message = handler.telegram.send_message.call_args[0][0]

    # Check each line of the expected message
    expected_lines = [
        "🔄 Proxy Implementation Upgrade Detected",
        f"Proxy Contract: {result.data['contract_address']}",
        f"New Implementation: {result.data['implementation_address']}",
    ]

    for line in expected_lines:
        assert line in message, f"Expected line not found in message: {line}"


@pytest.mark.asyncio
async def test_handle_upgrade_out_of_scope(handler, proxy_upgrade_event):
    """Test handling of an out-of-scope proxy upgrade event"""
    # Mock is_contract_in_scope to return False
    handler.is_contract_in_scope = AsyncMock(return_value=False)

    # Set up the context
    handler.context = {"payload": proxy_upgrade_event}

    # Handle the event
    result = await handler.handle()

    # Verify success but out of scope
    assert result.success is True
    assert result.data["found_upgrade"] is True
    assert result.data["in_scope"] is False

    # Verify no Telegram notification was sent
    handler.telegram.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_handle_non_upgrade_event(handler):
    """Test handling of a non-upgrade event"""
    # Mock is_contract_in_scope
    handler.is_contract_in_scope = AsyncMock()

    # Set up context with event that doesn't contain upgrade logs
    handler.context = {
        "payload": {
            "source": "ethereum",
            "logs": [
                {
                    "address": "0x1234...",
                    "topics": ["0xdifferent_topic"],
                }
            ],
        }
    }

    # Handle the event
    result = await handler.handle()

    # Verify no upgrade was found
    assert result.success is True
    assert result.data["found_upgrade"] is False

    # Verify no scope check or notification
    handler.is_contract_in_scope.assert_not_called()
    handler.telegram.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_handle_invalid_payload(handler):
    """Test handling of invalid payload"""
    # Set up context with invalid payload
    handler.context = {"payload": None}

    # Handle the event
    result = await handler.handle()

    # Verify failure
    assert result.success is False
    assert "error" in result.data

    # Verify no notification was sent
    handler.telegram.send_message.assert_not_called()
