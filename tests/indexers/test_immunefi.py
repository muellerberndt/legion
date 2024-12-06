import pytest
from unittest.mock import Mock, patch, AsyncMock, call, PropertyMock
from src.indexers.immunefi import ImmunefiIndexer
from src.models.base import Project, Asset, AssetType
from src.handlers.base import HandlerTrigger
from src.util.logging import Logger
import os

@pytest.fixture
def mock_session():
    session = AsyncMock()
    
    # Setup query mock - this needs to be a regular Mock for filter chains
    mock_query = Mock()
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None
    mock_query.all.return_value = []  # Return empty list by default
    
    # Make query a regular method that returns the mock_query
    session.query = Mock(return_value=mock_query)
    
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
