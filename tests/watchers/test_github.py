import pytest
from unittest.mock import Mock, patch, AsyncMock
from aiohttp import web
from src.watchers.github import GitHubWatcher
from src.handlers.base import HandlerTrigger
import json

@pytest.fixture
def mock_webhook_server():
    server = AsyncMock()
    server.register_endpoint = Mock()
    return server

@pytest.fixture
def github_watcher(mock_webhook_server):
    with patch('src.watchers.webhook_server.WebhookServer.get_instance', new_callable=AsyncMock) as mock_get_instance:
        mock_get_instance.return_value = mock_webhook_server
        watcher = GitHubWatcher()
        watcher.webhook_secret = "test_secret"  # Set test secret
        watcher.webhook_server = mock_webhook_server  # Set server directly
        return watcher

@pytest.fixture
def mock_request():
    request = Mock(spec=web.Request)
    request.headers = {
        'X-Hub-Signature-256': 'sha256=test',
        'X-GitHub-Event': 'push',
        'Content-Type': 'application/json'
    }
    return request

@pytest.mark.asyncio
async def test_push_webhook(github_watcher, mock_request):
    """Test handling of GitHub push webhook"""
    # Setup mock payload
    payload = {
        'repository': {
            'full_name': 'test/repo'
        },
        'ref': 'refs/heads/main',
        'commits': [
            {
                'id': 'abc123',
                'message': 'Test commit'
            }
        ]
    }
    mock_request.json = AsyncMock(return_value=payload)
    
    # Setup event bus mock
    github_watcher.event_bus.trigger_event = Mock()
    
    # Handle webhook
    response = await github_watcher.handle_webhook(mock_request)
    
    # Verify response
    assert response.status == 200
    
    # Verify event was triggered
    github_watcher.event_bus.trigger_event.assert_called_once_with(
        HandlerTrigger.GITHUB_PUSH,
        {
            'repository': 'test/repo',
            'branch': 'main',
            'commits': payload['commits']
        }
    )

@pytest.mark.asyncio
async def test_pr_webhook(github_watcher, mock_request):
    """Test handling of GitHub PR webhook"""
    # Setup PR payload
    payload = {
        'action': 'opened',
        'pull_request': {
            'title': 'Test PR',
            'body': 'Test description'
        },
        'repository': {
            'full_name': 'test/repo'
        }
    }
    mock_request.json = AsyncMock(return_value=payload)
    mock_request.headers['X-GitHub-Event'] = 'pull_request'
    
    # Setup event bus mock
    github_watcher.event_bus.trigger_event = Mock()
    
    # Handle webhook
    response = await github_watcher.handle_webhook(mock_request)
    
    # Verify response
    assert response.status == 200
    
    # Verify event was triggered
    github_watcher.event_bus.trigger_event.assert_called_once_with(
        HandlerTrigger.GITHUB_PR,
        {'payload': payload}
    )

@pytest.mark.asyncio
async def test_form_encoded_webhook(github_watcher, mock_request):
    """Test handling of form-encoded webhook payload"""
    # Setup form-encoded payload
    payload = {
        'repository': {
            'full_name': 'test/repo'
        },
        'ref': 'refs/heads/main',
        'commits': [
            {
                'id': 'abc123',
                'message': 'Test commit'
            }
        ]
    }
    mock_request.headers['Content-Type'] = 'application/x-www-form-urlencoded'
    mock_request.post = AsyncMock(return_value={'payload': json.dumps(payload)})
    
    # Setup event bus mock
    github_watcher.event_bus.trigger_event = Mock()
    
    # Handle webhook
    response = await github_watcher.handle_webhook(mock_request)
    
    # Verify response
    assert response.status == 200
    
    # Verify event was triggered
    github_watcher.event_bus.trigger_event.assert_called_once_with(
        HandlerTrigger.GITHUB_PUSH,
        {
            'repository': 'test/repo',
            'branch': 'main',
            'commits': payload['commits']
        }
    )

@pytest.mark.asyncio
async def test_invalid_json(github_watcher, mock_request):
    """Test handling of invalid JSON payload"""
    mock_request.json = AsyncMock(side_effect=json.JSONDecodeError('Invalid JSON', '', 0))
    
    # Handle webhook
    response = await github_watcher.handle_webhook(mock_request)
    
    # Verify error response
    assert response.status == 400
    assert 'Invalid JSON' in response._body.decode() 