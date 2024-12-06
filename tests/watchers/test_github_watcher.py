import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone, timedelta
from src.watchers.github import GitHubWatcher
from src.handlers.base import HandlerTrigger
from src.models.github import GitHubRepoState
from src.util.logging import Logger

logger = Logger("TestGitHubWatcher")

@pytest.fixture
def mock_session():
    """Mock aiohttp ClientSession"""
    session = AsyncMock()
    session.get = AsyncMock()
    return session

@pytest.fixture
def mock_db_session():
    """Mock database session"""
    session = AsyncMock()
    
    # Create a mock repo state that will be returned by get()
    repo_state = Mock()
    repo_state.last_commit_sha = 'old-sha'
    repo_state.last_pr_number = 1
    
    # Set up the get method to return our mock state
    async def get_mock(model_class, key):
        logger.debug(f"Mock get called with: {model_class=}, {key=}")
        if key == 'https://github.com/owner/repo':
            logger.debug("Returning mock repo state")
            return repo_state
        logger.debug("Returning None")
        return None
        
    session.get = AsyncMock(side_effect=get_mock)
    session.add = AsyncMock()
    session.commit = AsyncMock()
    
    # Set up context manager
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    
    return session

@pytest.fixture
async def watcher(mock_session, mock_db_session):
    """Create a GitHub watcher instance"""
    with patch('src.config.config.Config') as mock_config, \
         patch('src.backend.database.DBSessionMixin.get_async_session') as mock_get_session:
        # Mock config
        config = Mock()
        config.get.return_value = {
            'poll_interval': 300,  # 5 minutes
            'api_token': 'test-token'  # Optional token
        }
        mock_config.return_value = config
        
        # Create a mock context manager
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_db_session)
        cm.__aexit__ = AsyncMock(return_value=None)
        mock_get_session.return_value = cm
        
        # Create watcher and initialize it
        watcher = GitHubWatcher()
        watcher.session = mock_session  # Set the session directly
        await watcher.initialize()  # Initialize the watcher
        return watcher

@pytest.mark.asyncio
async def test_check_repo_updates(watcher, mock_session, mock_db_session):
    """Test checking repository updates"""
    # Mock repo data
    repo = {
        'repo_url': 'https://github.com/owner/repo',
        'last_commit_sha': 'old-sha',
        'last_pr_number': 1,
        'last_check': datetime.now(timezone.utc) - timedelta(hours=1)
    }
    
    # Mock API responses
    commits_response = AsyncMock()
    commits_response.status = 200
    await commits_response.json.return_value = [
        {'sha': 'new-sha', 'commit': {'message': 'New commit'}}
    ]
    
    prs_response = AsyncMock()
    prs_response.status = 200
    await prs_response.json.return_value = [
        {
            'number': 2,
            'title': 'New PR',
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
    ]
    
    # Set up session mock to return responses in order
    mock_session.get = AsyncMock()
    mock_session.get.side_effect = [commits_response, prs_response]
    
    # Check for updates
    logger.debug("Calling _check_repo_updates")
    events = await watcher._check_repo_updates(repo)
    logger.debug(f"Got events: {events}")
    
    # Verify events were generated
    assert len(events) == 2
    
    # Verify commit event
    commit_event = next(e for e in events if e['trigger'] == HandlerTrigger.GITHUB_PUSH)
    assert commit_event['data']['repo_url'] == repo['repo_url']
    assert commit_event['data']['commit']['sha'] == 'new-sha'
    
    # Verify PR event
    pr_event = next(e for e in events if e['trigger'] == HandlerTrigger.GITHUB_PR)
    assert pr_event['data']['repo_url'] == repo['repo_url']
    assert pr_event['data']['pull_request']['number'] == 2

@pytest.mark.asyncio
async def test_no_updates(watcher, mock_session, mock_db_session):
    """Test when there are no updates"""
    # Mock repo data with recent updates
    repo = {
        'repo_url': 'https://github.com/owner/repo',
        'last_commit_sha': 'current-sha',
        'last_pr_number': 2,
        'last_check': datetime.now(timezone.utc) - timedelta(minutes=5)
    }
    
    # Mock API responses with no new data
    commits_response = AsyncMock()
    commits_response.status = 200
    commits_response.json.return_value = [
        {'sha': 'current-sha', 'commit': {'message': 'Old commit'}}
    ]
    
    prs_response = AsyncMock()
    prs_response.status = 200
    prs_response.json.return_value = [
        {
            'number': 2,
            'title': 'Old PR',
            'updated_at': (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        }
    ]
    
    # Set up session mock
    mock_session.get = AsyncMock()
    mock_session.get.side_effect = [commits_response, prs_response]
    
    # Mock the database session context manager
    with patch('src.backend.database.DBSessionMixin.get_async_session') as mock_get_session:
        mock_get_session.return_value.__aenter__.return_value = mock_db_session
        
        # Check for updates
        events = await watcher._check_repo_updates(repo)
        
        # Verify no events were generated
        assert len(events) == 0

@pytest.mark.asyncio
async def test_api_error_handling(watcher, mock_session, mock_db_session):
    """Test handling API errors gracefully"""
    # Mock repo data
    repo = {
        'repo_url': 'https://github.com/owner/repo',
        'last_commit_sha': None,
        'last_pr_number': None,
        'last_check': None
    }
    
    # Mock API error responses
    error_response = AsyncMock()
    error_response.status = 403
    mock_session.get = AsyncMock(return_value=error_response)
    
    # Mock the database session context manager
    with patch('src.backend.database.DBSessionMixin.get_async_session') as mock_get_session:
        mock_get_session.return_value.__aenter__.return_value = mock_db_session
        
        # Check for updates
        events = await watcher._check_repo_updates(repo)
        
        # Verify no events were generated
        assert len(events) == 0

@pytest.mark.asyncio
async def test_parse_repo_url():
    """Test parsing GitHub repository URLs"""
    watcher = GitHubWatcher()
    
    # Test valid URL
    owner, repo = watcher._parse_repo_url('https://github.com/owner/repo')
    assert owner == 'owner'
    assert repo == 'repo'
    
    # Test URL with extra parts
    owner, repo = watcher._parse_repo_url('https://github.com/owner/repo/tree/main')
    assert owner == 'owner'
    assert repo == 'repo'
    
    # Test invalid URL
    owner, repo = watcher._parse_repo_url('https://not-github.com/owner/repo')
    assert owner is None
    assert repo is None 