"""Tests for webhook handlers"""

import pytest
from aiohttp import web
from unittest.mock import AsyncMock, Mock, patch
from src.webhooks.handlers import QuicknodeWebhookHandler
from src.handlers.base import HandlerTrigger


@pytest.fixture
def mock_handler_registry():
    registry = Mock()
    registry.trigger_event = AsyncMock()
    return registry


@pytest.fixture
def quicknode_handler(mock_handler_registry):
    handler = QuicknodeWebhookHandler()
    handler.handler_registry = mock_handler_registry
    return handler


@pytest.mark.asyncio
async def test_quicknode_handler_valid_payload(quicknode_handler):
    """Test handling a valid Quicknode webhook payload"""
    # Create test request with payload
    test_payload = {
        "payload": [
            {
                "eventId": "test-event-123",
                "blockNumber": "0x123",
                "transactionHash": "0xabc...",
            }
        ]
    }

    async def mock_json():
        return test_payload

    request = Mock()
    request.json = mock_json

    # Mock web.Response
    mock_response = Mock(spec=web.Response)
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value="OK")

    with patch("aiohttp.web.Response", return_value=mock_response):
        # Handle request
        response = await quicknode_handler.handle(request)

        # Verify response
        assert response.status == 200
        assert await response.text() == "OK"

        # Verify event was triggered
        quicknode_handler.handler_registry.trigger_event.assert_called_once_with(
            HandlerTrigger.BLOCKCHAIN_EVENT, {"source": "quicknode", "payload": test_payload["payload"][0]}
        )


@pytest.mark.asyncio
async def test_quicknode_handler_invalid_payload(quicknode_handler):
    """Test handling an invalid Quicknode webhook payload"""

    async def mock_json():
        raise ValueError("Invalid JSON")

    request = Mock()
    request.json = mock_json

    # Mock web.Response
    mock_response = Mock(spec=web.Response)
    mock_response.status = 500
    mock_response.text = AsyncMock(return_value="Invalid JSON")

    with patch("aiohttp.web.Response", return_value=mock_response):
        # Handle request
        response = await quicknode_handler.handle(request)

        # Verify error response
        assert response.status == 500
        assert await response.text() == "Invalid JSON"

        # Verify no event was triggered
        quicknode_handler.handler_registry.trigger_event.assert_not_called()
