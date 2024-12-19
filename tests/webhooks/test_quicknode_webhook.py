"""Integration tests for QuickNode webhook endpoint"""

import pytest
from unittest.mock import patch, AsyncMock, Mock

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
        from src.webhooks.server import WebhookServer

        server = WebhookServer()
        app = server.app
        app["webhook_server"] = server
        yield app


@pytest.fixture
async def client(aiohttp_client_cleanup, app):
    """Create test client"""
    return await aiohttp_client_cleanup(app)


@pytest.mark.asyncio
async def test_quicknode_webhook_endpoint(client, mock_handler_registry, quicknode_alert):
    """Test QuickNode webhook HTTP endpoint"""
    # Test valid request
    response = await client.post("/webhooks/quicknode", json=quicknode_alert, headers={"Content-Type": "application/json"})
    assert response.status == 200

    # Test invalid content type
    response = await client.post("/webhooks/quicknode", data="not json", headers={"Content-Type": "text/plain"})
    assert response.status == 400

    # Test missing payload
    response = await client.post("/webhooks/quicknode", json={"type": "invalid"}, headers={"Content-Type": "application/json"})
    assert response.status == 400
