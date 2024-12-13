"""Tests for webhook server"""

import pytest
from aiohttp import web
from unittest.mock import Mock, AsyncMock, patch
from src.webhooks.server import WebhookServer
from src.webhooks.handlers import WebhookHandler


class MockWebhookHandler(WebhookHandler):
    """Mock handler for testing"""

    async def handle(self, request: web.Request) -> web.Response:
        mock_response = Mock(spec=web.Response)
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="Mock handler response")
        return mock_response


@pytest.fixture
async def webhook_server():
    """Create a test webhook server"""
    server = WebhookServer()
    # Clear any existing handlers for testing
    server.handlers = {}
    yield server
    await server.stop()


@pytest.mark.asyncio
async def test_server_singleton():
    """Test that WebhookServer is a singleton"""
    server1 = await WebhookServer.get_instance()
    server2 = await WebhookServer.get_instance()
    assert server1 is server2


@pytest.mark.asyncio
async def test_register_handler(webhook_server):
    """Test registering a webhook handler"""
    handler = MockWebhookHandler()
    webhook_server.register_handler("/test", handler)

    assert "/webhooks/test" in webhook_server.handlers
    assert webhook_server.handlers["/webhooks/test"] is handler


@pytest.mark.asyncio
async def test_handle_webhook(webhook_server):
    """Test webhook handling"""
    # Register mock handler
    handler = MockWebhookHandler()
    webhook_server.register_handler("/test", handler)

    # Create test request
    request = Mock()
    request.path = "/webhooks/test"

    # Create mock response without using spec
    mock_response = Mock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value="Mock handler response")

    with patch("aiohttp.web.Response", return_value=mock_response):
        # Handle request
        response = await webhook_server._handle_webhook(request)

        # Verify response
        assert response.status == 200
        assert await response.text() == "Mock handler response"


@pytest.mark.asyncio
async def test_handle_webhook_not_found(webhook_server):
    """Test handling request for non-existent handler"""
    request = Mock()
    request.path = "/webhooks/nonexistent"

    # Mock web.Response
    mock_response = Mock(spec=web.Response)
    mock_response.status = 404
    mock_response.text = AsyncMock(return_value="No handler registered for path: /webhooks/nonexistent")

    with patch("aiohttp.web.Response", return_value=mock_response):
        response = await webhook_server._handle_webhook(request)

        assert response.status == 404
        assert await response.text() == "No handler registered for path: /webhooks/nonexistent"


@pytest.mark.asyncio
async def test_server_start_stop(webhook_server):
    """Test starting and stopping the server"""
    # Start server
    await webhook_server.start(port=8081)
    assert webhook_server.runner is not None
    assert webhook_server.port == 8081

    # Try starting again
    await webhook_server.start(port=8081)  # Should log warning but not fail

    # Stop server
    await webhook_server.stop()
    assert webhook_server.runner is None
