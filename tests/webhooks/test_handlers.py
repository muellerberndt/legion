"""Unit tests for webhook handlers"""

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
async def test_quicknode_handler_valid_payload(mock_handler_registry):
    """Test QuickNode webhook handler with valid payload"""
    handler = QuicknodeWebhookHandler()
    handler.handler_registry = mock_handler_registry

    # Create mock request with valid payload
    mock_request = Mock()
    mock_request.headers = {"Content-Type": "application/json"}
    mock_request.content_type = "application/json"
    mock_request.json = AsyncMock(return_value=[{"logs": [{"topics": ["topic1", "topic2"], "data": "0x"}]}])
    mock_request.text = AsyncMock(return_value='[{"logs":[{"topics":["topic1","topic2"],"data":"0x"}]}]')

    response = await handler.handle(mock_request)

    assert response.status == 200
    mock_handler_registry.trigger_event.assert_called_once()


@pytest.mark.asyncio
async def test_quicknode_handler_validation(quicknode_handler):
    """Test QuickNode handler payload validation"""
    test_cases = [
        ({"type": "invalid"}, "Invalid payload format"),
        ({"payload": None}, "Invalid payload format"),
        ({"payload": [{}]}, "Missing required logs"),
    ]

    for payload, expected_error in test_cases:
        request = Mock()
        request.json = AsyncMock(return_value=payload)

        # Mock web.Response
        mock_response = Mock(spec=web.Response)
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value=expected_error)

        with patch("aiohttp.web.Response", return_value=mock_response):
            response = await quicknode_handler.handle(request)
            assert response.status == 400
            response_text = await response.text()
            assert expected_error in response_text
            quicknode_handler.handler_registry.trigger_event.assert_not_called()
