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
    
    # Setup query mock - this needs to be a regular Mock for filter chains
    mock_query = Mock()
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None
    mock_query.all.return_value = []  # Return empty list by default
    
    # Make query a regular method that returns the mock_query
    session.query = Mock(return_value=mock_query)
    
    # Make add, delete, and commit regular synchronous operations
    session.add = Mock()
    session.delete = Mock()
    session.commit = Mock()
    
    # Setup context manager
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    
    return session

@pytest.fixture
def mock_response():
    response = AsyncMock()
    response.raise_for_status = AsyncMock()
    response.json = AsyncMock(return_value={})
    return response

@pytest.fixture
def mock_handler_registry():
    registry = Mock()
    # Use AsyncMock for trigger_event since it's an async operation
    registry.trigger_event = AsyncMock()
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

@pytest.fixture
def sample_bounty_data():
    return {
        'id': '123',
        'title': 'Test Project',
        'description': 'Test Description',
        'assets': [],
        'launchDate': '2023-01-01',
        'updatedDate': '2023-01-02',
        'maxBounty': '100000',
        'ecosystem': 'ethereum',
        'productType': 'defi',
        'programType': 'public',
        'projectType': 'bounty',
        'language': 'Solidity',
        'features': []
    }

@pytest.fixture
def updated_bounty_data():
    return {
        'id': '123',
        'title': 'Test Project',
        'description': 'Updated Description',
        'assets': [],
        'launchDate': '2023-01-01',
        'updatedDate': '2023-01-03',
        'maxBounty': '50000',
        'ecosystem': 'ethereum',
        'productType': 'defi',
        'programType': 'public',
        'projectType': 'bounty',
        'language': 'Solidity',
        'features': []
    }

@pytest.mark.asyncio
async def test_process_bounty_new_project(mock_session, mock_handler_registry):
    """Test processing a new bounty project"""
    indexer = ImmunefiIndexer(mock_session)
    indexer.handler_registry = mock_handler_registry
    
    # Setup mock query to return no existing project
    mock_session.query().filter().first.return_value = None
    
    bounty_data = {
        'project': 'Test Project',
        'description': 'Test Description',
        'ecosystem': ['Ethereum'],
        'productType': ['DeFi'],
        'programType': ['Bug Bounty'],
        'projectType': ['Smart Contract'],
        'language': ['Solidity'],
        'features': ['Staking'],
        'maxBounty': '100000',
        'assets': []
    }
    
    await indexer.process_bounty(bounty_data)
    
    # Verify project was created
    assert mock_session.add.call_count == 1
    assert mock_session.commit.call_count == 1
    
    # Verify event was triggered
    mock_handler_registry.trigger_event.assert_awaited_once()
    event_call = mock_handler_registry.trigger_event.call_args[0]
    assert event_call[0] == HandlerTrigger.NEW_PROJECT
    assert event_call[1]['project'] == mock_session.add.call_args[0][0]

@pytest.mark.asyncio
async def test_process_bounty_update_project(mock_session, mock_handler_registry, mock_project):
    """Test processing an existing bounty project with changes"""
    indexer = ImmunefiIndexer(mock_session)
    indexer.handler_registry = mock_handler_registry
    
    # Setup mock query to return existing project
    mock_session.query().filter().first.return_value = mock_project
    
    # Setup initial project state
    mock_project.description = "Old Description"
    mock_project.keywords = ["Old"]
    mock_project.extra_data = {
        'maxBounty': '50000',
        'ecosystem': ['BSC']
    }
    
    bounty_data = {
        'project': mock_project.name,
        'description': 'New Description',
        'ecosystem': ['Ethereum'],
        'productType': ['DeFi'],
        'maxBounty': '100000',
        'assets': []
    }
    
    await indexer.process_bounty(bounty_data)
    
    # Verify changes were saved
    assert mock_project.description == 'New Description'
    assert 'Ethereum' in mock_project.keywords
    assert mock_project.extra_data['maxBounty'] == '100000'
    assert mock_session.commit.call_count == 2  # One for project update, one for cleanup
    
    # Verify update event was triggered
    assert mock_handler_registry.trigger_event.call_count == 1  # Project update
    event_calls = mock_handler_registry.trigger_event.call_args_list
    
    # First call should be project update
    first_call = event_calls[0][0]
    assert first_call[0] == HandlerTrigger.PROJECT_UPDATE
    assert first_call[1]['project'] == mock_project
    assert first_call[1]['old_project'].description == "Old Description"

@pytest.mark.asyncio
async def test_process_bounty_no_changes(mock_session, mock_handler_registry, mock_project):
    """Test processing an existing bounty project with no changes"""
    indexer = ImmunefiIndexer(mock_session)
    indexer.handler_registry = mock_handler_registry
    
    # Setup mock query to return existing project
    mock_session.query().filter().first.return_value = mock_project
    
    # Setup project state with a real dictionary
    mock_project.description = "Test Description"
    mock_project.keywords = ["Ethereum", "DeFi"]
    mock_project.extra_data = {
        'maxBounty': '100000',
        'ecosystem': ['Ethereum'],
        'productType': ['DeFi'],
        'assets': [],
        'launchDate': None,
        'updatedDate': None,
        'programType': None,
        'projectType': None,
        'language': None,
        'features': None
    }
    
    # Create bounty data with exactly the same values
    bounty_data = {
        'project': mock_project.name,
        'description': 'Test Description',
        'ecosystem': ['Ethereum'],
        'productType': ['DeFi'],
        'maxBounty': '100000',
        'assets': []
    }
    
    await indexer.process_bounty(bounty_data)
    
    # Verify no update event was triggered (no changes)
    mock_handler_registry.trigger_event.assert_not_awaited()

@pytest.mark.asyncio
async def test_cleanup_removed_projects(mock_session, mock_handler_registry, mock_project, mock_file_ops):
    """Test cleanup of removed projects"""
    indexer = ImmunefiIndexer(mock_session)
    indexer.handler_registry = mock_handler_registry
    
    # Setup mock query to return existing projects
    mock_session.query().filter().all.return_value = [mock_project]
    
    # Add some assets to the project
    asset1 = Mock(spec=Asset)
    asset1.id = "test1"
    asset1.local_path = "/test/path1"
    asset2 = Mock(spec=Asset)
    asset2.id = "test2"
    asset2.local_path = "/test/path2"
    mock_project.assets = [asset1, asset2]
    
    # Call cleanup with empty current projects (all should be removed)
    await indexer.cleanup_removed_projects(set())
    
    # Verify project and assets were deleted
    assert mock_session.delete.call_count == 3  # Project + 2 assets
    assert mock_session.commit.call_count == 2  # One for old projects update, one for cleanup
    
    # Verify events were triggered
    assert mock_handler_registry.trigger_event.call_count == 3  # Two asset removals + one project removal
    event_calls = mock_handler_registry.trigger_event.call_args_list
    
    # First two calls should be asset removals
    for i in range(2):
        call = event_calls[i][0]
        assert call[0] == HandlerTrigger.ASSET_REMOVE
        assert call[1]['project'] == mock_project
    
    # Last call should be project removal
    last_call = event_calls[-1][0]
    assert last_call[0] == HandlerTrigger.PROJECT_REMOVE
    assert last_call[1]['project'] == mock_project
    assert last_call[1]['removed'] is True
