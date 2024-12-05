import os
os.environ['LOG_LEVEL'] = 'DEBUG'

import pytest
from unittest.mock import Mock, patch, AsyncMock, call, PropertyMock
from src.indexers.immunefi import ImmunefiIndexer
from src.models.base import Project, Asset, AssetType
from src.handlers.base import HandlerTrigger
from src.util.logging import Logger, LogConfig
import logging

# Configure logging
LogConfig.configure_logging("DEBUG")

@pytest.fixture(autouse=True)
def setup_logging():
    """Configure logging for tests"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

@pytest.fixture
def mock_session():
    session = Mock()
    
    # Setup query mock
    mock_query = Mock()
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None
    mock_query.all.return_value = []  # Return empty list by default
    session.query.return_value = mock_query
    
    # Setup context manager
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=None)
    
    return session

@pytest.fixture
def mock_handler_registry():
    registry = Mock()
    registry.trigger_event = Mock()
    return registry

@pytest.fixture
def mock_project():
    project = Mock(spec=Project)
    project.id = 1
    project.name = "Test Project"
    project.description = "Test Description"
    project.project_type = "immunefi"
    project.extra_data = {}
    project.assets = []  # Use a real list directly
    return project

@pytest.fixture
def mock_asset():
    asset = Mock(spec=Asset)
    asset.id = "https://github.com/test/repo/blob/main/test.sol"
    asset.asset_type = AssetType.GITHUB_FILE
    asset.local_path = "/test/path"
    asset.source_url = "https://github.com/test/repo/blob/main/test.sol"
    asset.extra_data = {"revision": "abc123"}
    
    # Add debug logging
    logger = Logger("TestFixtures")
    logger.debug(f"Created mock asset with properties:")
    logger.debug(f"  id: {asset.id}")
    logger.debug(f"  type: {asset.asset_type}")
    logger.debug(f"  path: {asset.local_path}")
    logger.debug(f"  url: {asset.source_url}")
    logger.debug(f"  extra_data: {asset.extra_data}")
    
    return asset

@pytest.fixture
def mock_file_ops():
    with patch('os.path.exists') as mock_exists, \
         patch('os.path.isdir') as mock_isdir, \
         patch('shutil.rmtree') as mock_rmtree, \
         patch('os.remove') as mock_remove, \
         patch('os.makedirs') as mock_makedirs:
        
        # Set default behaviors
        mock_exists.return_value = True
        mock_isdir.return_value = False  # Default to file, not directory
        
        yield {
            'exists': mock_exists,
            'isdir': mock_isdir,
            'rmtree': mock_rmtree,
            'remove': mock_remove,
            'makedirs': mock_makedirs
        }

@pytest.mark.asyncio
@patch('aiohttp.ClientSession.get')
@patch('src.config.config.Config')
async def test_new_project_detection(mock_config, mock_get, mock_session, mock_handler_registry):
    """Test detection of a new untracked project"""
    # Setup mock response with a new project
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value=[{
        'project': 'New Project',
        'description': 'New Description',
        'assets': []
    }])
    mock_get.return_value.__aenter__.return_value = mock_response
    
    # Setup config mock
    mock_config.return_value.data_dir = "./test_data"
    
    # Run indexer
    indexer = ImmunefiIndexer(session=mock_session)
    indexer.handler_registry = mock_handler_registry
    await indexer.index()
    
    # Verify project was created and event was triggered
    assert mock_session.add.call_count > 0, "Session.add() was not called"
    added_project = mock_session.add.call_args[0][0]
    mock_handler_registry.trigger_event.assert_called_once_with(
        HandlerTrigger.NEW_PROJECT,
        {'project': added_project}
    )

@pytest.mark.asyncio
@patch('aiohttp.ClientSession.get')
@patch('src.config.config.Config')
@patch('os.makedirs')
async def test_new_asset_detection(mock_makedirs, mock_config, mock_get, mock_session, mock_handler_registry, mock_project):
    """Test detection of a new asset added to existing project"""
    # Setup existing project in session
    mock_project_query = Mock()
    mock_project_query.first.return_value = mock_project
    mock_project_query.all.return_value = [mock_project]
    
    mock_asset_query = Mock()
    mock_asset_query.first.return_value = None
    
    def query_side_effect(model):
        if model == Project:
            return mock_project_query
        return mock_asset_query
        
    mock_session.query.side_effect = query_side_effect
    mock_project_query.filter.return_value = mock_project_query
    mock_asset_query.filter.return_value = mock_asset_query
    
    # Setup mock response with new asset
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value=[{
        'project': 'Test Project',
        'description': 'Test Description',
        'assets': [{
            'url': 'https://github.com/test/repo',
            'revision': 'abc123'
        }]
    }])
    mock_get.return_value.__aenter__.return_value = mock_response
    
    # Setup config mock
    mock_config.return_value.data_dir = "./test_data"
    
    # Run indexer
    indexer = ImmunefiIndexer(session=mock_session)
    indexer.handler_registry = mock_handler_registry
    
    # Mock asset download
    with patch('src.indexers.immunefi.fetch_github_repo', new_callable=AsyncMock):
        await indexer.index()
    
    # Verify new asset was added and event was triggered
    assert mock_session.add.call_count > 0, "Session.add() was not called"
    added_asset = mock_session.add.call_args[0][0]
    assert added_asset.id == "https://github.com/test/repo"
    
    mock_handler_registry.trigger_event.assert_called_with(
        HandlerTrigger.NEW_ASSET,
        {'asset': added_asset}
    )

@pytest.mark.asyncio
@patch('aiohttp.ClientSession.get')
@patch('src.config.config.Config')
@patch('os.makedirs')
@patch('os.path.exists')
async def test_asset_revision_update(mock_exists, mock_makedirs, mock_config, mock_get, mock_session, mock_handler_registry, mock_project, mock_asset):
    """Test detection of an asset revision update"""
    # Setup existing project with asset
    mock_project.assets = [mock_asset]  # Use a real list for assets
    mock_project_query = Mock()
    mock_project_query.first.return_value = mock_project
    mock_project_query.all.return_value = [mock_project]
    
    # Mock asset query to return the existing asset
    mock_asset_query = Mock()
    mock_asset_query.first.return_value = mock_asset  # Always return the existing asset
    
    def query_side_effect(model):
        if model == Project:
            return mock_project_query
        return mock_asset_query
        
    mock_session.query.side_effect = query_side_effect
    mock_project_query.filter.return_value = mock_project_query
    mock_asset_query.filter.return_value = mock_asset_query
    
    mock_exists.return_value = True
    
    # Setup mock response with updated revision
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value=[{
        'project': 'Test Project',
        'description': 'Test Description',
        'assets': [{
            'url': 'https://github.com/test/repo/blob/main/test.sol',  # Match the blob URL
            'revision': 'def456'  # New revision
        }]
    }])
    mock_get.return_value.__aenter__.return_value = mock_response
    
    # Setup config mock
    mock_config.return_value.data_dir = "./test_data"
    
    # Run indexer
    indexer = ImmunefiIndexer(session=mock_session, initialize_mode=False)
    indexer.handler_registry = mock_handler_registry
    
    # Mock asset download and file operations
    with patch('src.indexers.immunefi.fetch_github_file', new_callable=AsyncMock) as mock_fetch, \
         patch('shutil.copy2', new_callable=AsyncMock) as mock_copy, \
         patch('os.remove', new_callable=AsyncMock) as mock_remove:
        
        await indexer.index()
        
        # Verify asset update event was triggered with correct data
        event_calls = mock_handler_registry.trigger_event.call_args_list
        update_events = [
            call for call in event_calls 
            if call[0][0] == HandlerTrigger.ASSET_UPDATE
        ]
        
        assert len(update_events) > 0, "No ASSET_UPDATE events were triggered"
        
        # Find the revision update event (not removal event)
        update_event = None
        for call in update_events:
            event_data = call[0][1]
            if event_data.get('new_revision') == 'def456':
                update_event = call
                break
                
        assert update_event is not None, "No revision update event found"
        event_data = update_event[0][1]
        
        # Verify event data
        assert event_data['asset'] == mock_asset
        assert event_data['old_revision'] == 'abc123'
        assert event_data['new_revision'] == 'def456'
        assert event_data['old_path'].endswith('.old')
        assert event_data['new_path'] == mock_asset.local_path

@pytest.mark.asyncio
@patch('aiohttp.ClientSession.get')
@patch('src.config.config.Config')
async def test_asset_removal(mock_config, mock_get, mock_session, mock_handler_registry, mock_project, mock_asset, mock_file_ops):
    """Test detection of an asset being removed from a project"""
    # Setup existing project with asset
    mock_project.assets.append(mock_asset)
    
    mock_project_query = Mock()
    mock_project_query.first.return_value = mock_project
    mock_project_query.all.return_value = [mock_project]
    
    mock_asset_query = Mock()
    mock_asset_query.first.return_value = mock_asset
    
    def query_side_effect(model):
        if model == Project:
            return mock_project_query
        return mock_asset_query
        
    mock_session.query.side_effect = query_side_effect
    mock_project_query.filter.return_value = mock_project_query
    mock_asset_query.filter.return_value = mock_asset_query
    
    # Setup mock response with asset removed
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value=[{
        'project': 'Test Project',
        'description': 'Test Description',
        'assets': []  # Asset removed
    }])
    mock_get.return_value.__aenter__.return_value = mock_response
    
    # Setup config mock
    mock_config.return_value.data_dir = "./test_data"
    
    # Run indexer
    indexer = ImmunefiIndexer(session=mock_session)
    indexer.handler_registry = mock_handler_registry
    await indexer.index()
    
    # Verify asset removal event was triggered
    event_calls = mock_handler_registry.trigger_event.call_args_list
    removal_events = [
        call for call in event_calls 
        if call[0][0] == HandlerTrigger.ASSET_UPDATE and call[0][1].get('removed')
    ]
    assert len(removal_events) > 0, "No asset removal events were triggered"
    
    event_data = removal_events[0][0][1]
    assert event_data['asset'] == mock_asset
    assert event_data['old_revision'] == 'abc123'
    assert event_data['new_revision'] is None
    assert event_data['removed'] is True
    
    # Verify file cleanup
    mock_file_ops['exists'].assert_called_with(mock_asset.local_path)
    mock_file_ops['isdir'].assert_called_with(mock_asset.local_path)
    mock_file_ops['remove'].assert_called_with(mock_asset.local_path)
    
    # Verify database cleanup
    mock_session.delete.assert_called_with(mock_asset)
    mock_session.commit.assert_called()

@pytest.mark.asyncio
@patch('aiohttp.ClientSession.get')
@patch('src.config.config.Config')
async def test_no_events_in_initialize_mode(mock_config, mock_get, mock_session, mock_handler_registry):
    """Test that no events are triggered when in initialize mode"""
    # Setup mock response with new project and asset
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value=[{
        'project': 'New Project',
        'description': 'New Description',
        'assets': [{
            'url': 'https://github.com/test/repo',
            'revision': 'abc123'
        }]
    }])
    mock_get.return_value.__aenter__.return_value = mock_response
    
    # Setup config mock
    mock_config.return_value.data_dir = "./test_data"
    
    # Run indexer in initialize mode
    indexer = ImmunefiIndexer(session=mock_session, initialize_mode=True)
    indexer.handler_registry = mock_handler_registry
    
    # Mock asset download
    with patch('src.indexers.immunefi.fetch_github_repo', new_callable=AsyncMock):
        await indexer.index()
    
    # Verify no events were triggered
    mock_handler_registry.trigger_event.assert_not_called()