"""Integration tests for QuickNode webhook endpoint"""

import pytest
from unittest.mock import patch, AsyncMock, Mock
from src.webhooks.server import WebhookServer
from src.webhooks.handlers import QuicknodeWebhookHandler

pytest_plugins = ["pytest_aiohttp"]


@pytest.fixture
def mock_handler_registry():
    """Mock handler registry with async trigger_event method"""
    mock = Mock()
    mock.trigger_event = AsyncMock()
    return mock


@pytest.fixture
async def app(mock_handler_registry):
    """Create test application with mocked handler registry"""
    with patch("src.webhooks.handlers.HandlerRegistry") as mock_registry_class:
        mock_registry_class.return_value = mock_handler_registry

        # Create a fresh server instance
        server = WebhookServer()

        # Register the handler for testing
        handler = QuicknodeWebhookHandler()
        handler.handler_registry = mock_handler_registry  # Inject mock registry
        server.register_handler("/webhooks/quicknode", handler)

        yield server.app


@pytest.fixture
async def client(aiohttp_client, app):
    """Create test client"""
    return await aiohttp_client(app)


@pytest.mark.asyncio
async def test_quicknode_webhook_valid_request(client, mock_handler_registry, quicknode_alert):
    """Test QuickNode webhook with valid request"""
    response = await client.post("/webhooks/quicknode", json=quicknode_alert, headers={"Content-Type": "application/json"})
    assert response.status == 200
    mock_handler_registry.trigger_event.assert_called_once()


@pytest.mark.asyncio
async def test_quicknode_webhook_invalid_content_type(client, mock_handler_registry):
    """Test QuickNode webhook with invalid content type"""
    # Ensure we're using a fresh client for this test
    response = await client.post(
        "/webhooks/quicknode", data=b"not json", skip_auto_headers=["Content-Type"], headers={"Content-Type": "text/plain"}
    )

    # Get response details
    status = response.status
    text = await response.text()

    # Log response details for debugging
    print(f"Response status: {status}")
    print(f"Response text: {text}")
    print(f"Response headers: {dict(response.headers)}")

    # Assertions
    assert status == 400, f"Expected 400 but got {status}. Response text: {text}"
    assert "Invalid content type" in text
    mock_handler_registry.trigger_event.assert_not_called()


@pytest.mark.asyncio
async def test_quicknode_webhook_invalid_payload(client, mock_handler_registry):
    """Test QuickNode webhook with invalid payload format"""
    response = await client.post("/webhooks/quicknode", json={"type": "invalid"}, headers={"Content-Type": "application/json"})
    assert response.status == 400
    mock_handler_registry.trigger_event.assert_not_called()


@pytest.mark.asyncio
async def test_quicknode_webhook_invalid_event(client, mock_handler_registry):
    """Test QuickNode webhook with invalid event format"""
    response = await client.post(
        "/webhooks/quicknode", json=[{"invalid": "format"}], headers={"Content-Type": "application/json"}
    )
    assert response.status == 400
    mock_handler_registry.trigger_event.assert_not_called()
