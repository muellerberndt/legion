import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.indexers.immunefi import ImmunefiIndexer
from src.models.base import Project

@pytest.fixture
def mock_session():
    session = Mock()
    
    # Setup query mock
    mock_query = Mock()
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None
    session.query.return_value = mock_query
    
    # Setup context manager
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=None)
    
    return session

@pytest.mark.asyncio
@patch('aiohttp.ClientSession.get')
@patch('src.config.config.Config')
async def test_index(mock_config, mock_get, mock_session):
    # Setup mock response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value='[{"project": "Test Project", "description": "Test Description", "assets": []}]')
    mock_response.json = AsyncMock(return_value=[
        {
            'project': 'Test Project',
            'description': 'Test Description',
            'assets': []
        }
    ])
    mock_get.return_value.__aenter__.return_value = mock_response
    
    # Setup config mock
    config = Mock()
    config.data_dir = "./test_data"
    mock_config.return_value = config
    
    # Run indexer
    indexer = ImmunefiIndexer(session=mock_session, initialize_mode=True)
    await indexer.index()
    
    # Verify project was created
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
    
    # Verify the added project
    added_project = mock_session.add.call_args[0][0]
    assert isinstance(added_project, Project)
    assert added_project.name == 'Test Project'