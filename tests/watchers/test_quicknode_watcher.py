import pytest
from aiohttp import web
from src.watchers.quicknode import QuicknodeWatcher
from src.handlers.base import HandlerTrigger
from src.handlers.event_bus import EventBus
import json
from unittest.mock import AsyncMock
from aiohttp.test_utils import TestClient, TestServer

@pytest.fixture
def watcher():
    watcher = QuicknodeWatcher()
    # Mock the handler registry trigger_event method
    watcher.handler_registry.trigger_event = AsyncMock()
    return watcher

@pytest.fixture
async def test_client(watcher):
    """Create test application with client"""
    app = web.Application()
    
    # Register routes before starting server
    watcher.register_routes(app)
    
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    yield client, app
    await client.close()

async def test_initialize(watcher):
    """Test that initialize doesn't raise any errors"""
    await watcher.initialize()

async def test_check(watcher):
    """Test that check doesn't raise any errors"""
    result = await watcher.check()
    assert isinstance(result, list)
    assert len(result) == 0

@pytest.mark.asyncio
async def test_handle_webhook_valid_payload(watcher, test_client):
    """Test handling a valid webhook payload"""
    client, _ = test_client
    
    test_payload = {
        "payload": [{  # Wrap in payload array to match Quicknode format
            "eventId": "test-event-123",
            "blockNumber": "0x123",
            "transactionHash": "0xabc..."
        }]
    }
    
    resp = await client.post(
        "/webhooks/quicknode",
        json=test_payload,
        headers={"Content-Type": "application/json"}
    )
    
    assert resp.status == 200
    text = await resp.text()
    assert text == "OK"
    
    # Verify event was triggered
    watcher.handler_registry.trigger_event.assert_awaited_once_with(
        HandlerTrigger.BLOCKCHAIN_EVENT,
        {
            "source": "quicknode",
            "payload": test_payload["payload"][0]
        }
    )

@pytest.mark.asyncio
async def test_handle_webhook_invalid_payload(watcher, test_client):
    """Test handling an invalid webhook payload"""
    client, _ = test_client
    
    # Send invalid JSON
    resp = await client.post(
        "/webhooks/quicknode",
        data="invalid json",
        headers={"Content-Type": "application/json"}
    )
    
    assert resp.status == 500
    
    # Verify no event was triggered
    watcher.handler_registry.trigger_event.assert_not_called()

@pytest.mark.asyncio
async def test_event_triggering_without_event_bus(watcher, test_client):
    """Test webhook handling when event bus is not set"""
    client, app = test_client
    
    test_payload = {
        "eventId": "test-event-123",
        "blockNumber": "0x123",
        "transactionHash": "0xabc..."
    }
    
    # Create a new app without handler registry
    new_app = web.Application()
    watcher.handler_registry = None
    watcher.register_routes(new_app)
    
    new_server = TestServer(new_app)
    new_client = TestClient(new_server)
    await new_client.start_server()
    
    try:
        resp = await new_client.post(
            "/webhooks/quicknode",
            json=test_payload,
            headers={"Content-Type": "application/json"}
        )
        
        # Should still return OK even without handler registry
        assert resp.status == 200
        text = await resp.text()
        assert text == "OK"
    finally:
        await new_client.close()
    