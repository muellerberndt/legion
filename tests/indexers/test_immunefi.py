import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from src.indexers.immunefi import ImmunefiIndexer
from src.models.base import Project, Asset, AssetType
from src.handlers.base import HandlerTrigger


class SerializableMock(MagicMock):
    """A mock that can be properly serialized."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._serializable_dict = {}

    def _get_dict(self):
        """Get the serializable dictionary."""
        return self._serializable_dict

    def __str__(self):
        return str(self._get_dict())

    def __repr__(self):
        return str(self._get_dict())

    def to_dict(self):
        """Convert to dictionary for serialization."""
        return self._get_dict()

    def __getattr__(self, name):
        if name == "to_dict":
            return self._get_dict
        return super().__getattr__(name)


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
    project = SerializableMock(spec=Project)
    # Set attributes
    project.id = 1
    project.name = "Test Project"
    project.description = "Test Description"
    project.project_type = "bounty"
    project.project_source = "immunefi"
    project.extra_data = {}
    project.assets = []  # Use a real list directly
    project.keywords = []
    # Update serializable dict
    project._serializable_dict.update(
        {
            "id": 1,
            "name": "Test Project",
            "description": "Test Description",
            "project_type": "bounty",
            "project_source": "immunefi",
            "extra_data": {},
            "assets": [],
            "keywords": [],
        }
    )
    # Add to_dict method
    project.to_dict = lambda: project._serializable_dict
    return project


@pytest.fixture
def mock_asset():
    asset = SerializableMock(spec=Asset)
    # Set attributes
    asset.id = "https://github.com/test/repo/blob/main/test.sol"
    asset.asset_type = AssetType.GITHUB_FILE
    asset.local_path = "/test/path"
    asset.source_url = "https://github.com/test/repo/blob/main/test.sol"
    asset.extra_data = {}
    # Update serializable dict
    asset._serializable_dict.update(
        {
            "id": "https://github.com/test/repo/blob/main/test.sol",
            "asset_type": AssetType.GITHUB_FILE,
            "local_path": "/test/path",
            "source_url": "https://github.com/test/repo/blob/main/test.sol",
            "extra_data": {},
        }
    )
    # Add to_dict method
    asset.to_dict = lambda: asset._serializable_dict
    return asset


@pytest.fixture
def mock_file_ops():
    with (
        patch("os.path.exists") as mock_exists,
        patch("os.path.isdir") as mock_isdir,
        patch("shutil.rmtree") as mock_rmtree,
        patch("os.remove") as mock_remove,
        patch("os.makedirs") as mock_makedirs,
    ):

        # Set default behaviors
        mock_exists.return_value = True
        mock_isdir.return_value = False  # Default to file, not directory

        yield {
            "exists": mock_exists,
            "isdir": mock_isdir,
            "rmtree": mock_rmtree,
            "remove": mock_remove,
            "makedirs": mock_makedirs,
        }


@pytest.fixture
def sample_bounty_data():
    return {
        "id": "123",
        "title": "Test Project",
        "description": "Test Description",
        "assets": [],
        "launchDate": "2023-01-01",
        "updatedDate": "2023-01-02",
        "maxBounty": "100000",
        "ecosystem": "ethereum",
        "productType": "defi",
        "programType": "public",
        "projectType": "bounty",
        "language": "Solidity",
        "features": [],
    }


@pytest.fixture
def updated_bounty_data():
    return {
        "id": "123",
        "title": "Test Project",
        "description": "Updated Description",
        "assets": [],
        "launchDate": "2023-01-01",
        "updatedDate": "2023-01-03",
        "maxBounty": "50000",
        "ecosystem": "ethereum",
        "productType": "defi",
        "programType": "public",
        "projectType": "bounty",
        "language": "Solidity",
        "features": [],
    }


@pytest.mark.asyncio
async def test_process_bounty_new_project(mock_session, mock_handler_registry):
    """Test processing a new bounty project"""
    indexer = ImmunefiIndexer(mock_session)
    indexer.handler_registry = mock_handler_registry

    # Setup mock query to return no existing project
    mock_session.query().filter().first.return_value = None

    bounty_data = {
        "project": "Test Project",
        "description": "Test Description",
        "ecosystem": ["Ethereum"],
        "productType": ["DeFi"],
        "programType": ["Bug Bounty"],
        "projectType": ["Smart Contract"],
        "language": ["Solidity"],
        "features": ["Staking"],
        "maxBounty": "100000",
        "assets": [],
    }

    await indexer.process_bounty(bounty_data)

    # Verify project was created
    assert mock_session.add.call_count == 1
    assert mock_session.commit.call_count == 1

    # Get the created project
    created_project = mock_session.add.call_args[0][0]
    assert created_project.name == "Test Project"
    assert created_project.description == "Test Description"
    assert "Ethereum" in created_project.keywords
    assert "DeFi" in created_project.keywords
    assert created_project.project_type == "bounty"
    assert created_project.project_source == "immunefi"

    # Verify event was triggered
    mock_handler_registry.trigger_event.assert_awaited_once()
    event_call = mock_handler_registry.trigger_event.call_args[0]
    assert event_call[0] == HandlerTrigger.NEW_PROJECT

    # Verify serialized project data
    event_project = event_call[1]["project"]
    assert isinstance(event_project, dict)
    assert event_project["name"] == "Test Project"
    assert event_project["description"] == "Test Description"
    assert event_project["project_type"] == "bounty"
    assert event_project["project_source"] == "immunefi"


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
        "maxBounty": "100000",
        "ecosystem": ["Ethereum"],
        "productType": ["DeFi"],
        "launchDate": None,
        "updatedDate": None,
        "programType": None,
        "projectType": None,
        "language": None,
        "features": None,
    }
    mock_project.__dict__.update(
        {"description": "Test Description", "keywords": ["Ethereum", "DeFi"], "extra_data": mock_project.extra_data}
    )
    mock_project.assets = []  # Ensure assets is an empty list

    # Create bounty data with exactly the same values
    bounty_data = {
        "project": mock_project.name,
        "description": "Test Description",
        "ecosystem": ["Ethereum"],
        "productType": ["DeFi"],
        "maxBounty": "100000",
        "assets": [],
    }

    await indexer.process_bounty(bounty_data)

    # Verify no update event was triggered (no changes)
    mock_handler_registry.trigger_event.assert_not_awaited()
