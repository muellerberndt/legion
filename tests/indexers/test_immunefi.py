import pytest
from unittest.mock import Mock, patch, AsyncMock, call, PropertyMock
from src.indexers.immunefi import ImmunefiIndexer
from src.models.base import Project, Asset, AssetType
from src.handlers.base import HandlerTrigger
from src.util.logging import Logger
import os

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
    project.project_type = "bounty"
    project.project_source = "immunefi"
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
        if call[0][0] == HandlerTrigger.ASSET_REMOVE
    ]
    assert len(removal_events) > 0, "No asset removal events were triggered"
    
    # Verify event data
    event_data = removal_events[0][0][1]
    assert event_data['asset'] == mock_asset
    assert event_data['project'] == mock_project  # Add project to verification
    
    # Verify file cleanup
    mock_file_ops['exists'].assert_called_with(mock_asset.local_path)
    mock_file_ops['isdir'].assert_called_with(mock_asset.local_path)
    mock_file_ops['remove'].assert_called_with(mock_asset.local_path)
    
    # Verify database cleanup
    mock_session.delete.assert_called_with(mock_asset)
    mock_session.commit.assert_called()