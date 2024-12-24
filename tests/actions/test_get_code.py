import pytest
from unittest.mock import patch, MagicMock
from src.actions.get_code import GetCodeAction
from src.models.base import Asset, AssetType
from src.actions.result import ResultType


@pytest.fixture
def get_code_action():
    return GetCodeAction()


@pytest.fixture
def mock_db_session():
    with patch("src.actions.get_code.DBSessionMixin") as mock:
        session = MagicMock()
        mock.return_value.get_session.return_value.__enter__.return_value = session
        yield session


@pytest.mark.asyncio
async def test_get_code_github_file(get_code_action, mock_db_session, tmp_path):
    # Create a temporary file
    test_file = tmp_path / "test.sol"
    test_file.write_text("contract Test { }")

    # Mock the asset query
    mock_asset = MagicMock(spec=Asset)
    mock_asset.id = 1
    mock_asset.asset_type = AssetType.GITHUB_FILE
    mock_asset.local_path = str(test_file)
    mock_asset.get_code.return_value = "contract Test { }"
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_asset

    # Execute action
    result = await get_code_action.execute("1")

    # Verify result
    assert result.type == ResultType.TEXT
    assert result.content == "contract Test { }"


@pytest.mark.asyncio
async def test_get_code_deployed_contract(get_code_action, mock_db_session, tmp_path):
    # Create a temporary contract directory with multiple files
    contract_dir = tmp_path / "contract"
    contract_dir.mkdir()

    # Create test files
    (contract_dir / "main.sol").write_text("contract Main { }")
    (contract_dir / "lib.sol").write_text("library Lib { }")

    # Create a subdirectory with more files
    sub_dir = contract_dir / "utils"
    sub_dir.mkdir()
    (sub_dir / "helper.sol").write_text("contract Helper { }")

    # Expected content with all files
    expected_content = [
        "// File: main.sol\ncontract Main { }",
        "// File: lib.sol\nlibrary Lib { }",
        "// File: utils/helper.sol\ncontract Helper { }",
    ]

    # Mock the asset query
    mock_asset = MagicMock(spec=Asset)
    mock_asset.id = 2
    mock_asset.asset_type = AssetType.DEPLOYED_CONTRACT
    mock_asset.local_path = str(contract_dir)
    mock_asset.get_code.return_value = "\n".join(expected_content)
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_asset

    # Execute action
    result = await get_code_action.execute("2")

    # Verify result
    assert result.type == ResultType.TEXT
    for content in expected_content:
        assert content in result.content


@pytest.mark.asyncio
async def test_get_code_github_repo(get_code_action, mock_db_session):
    # Mock the asset query for a repo
    mock_asset = MagicMock(spec=Asset)
    mock_asset.id = 3
    mock_asset.asset_type = AssetType.GITHUB_REPO
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_asset

    # Execute action
    result = await get_code_action.execute("3")

    # Verify result
    assert result.type == ResultType.ERROR
    assert "not supported" in result.error.lower()


@pytest.mark.asyncio
async def test_get_code_invalid_id(get_code_action, mock_db_session):
    # Mock no asset found
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    # Execute action
    result = await get_code_action.execute("999")

    # Verify result
    assert result.type == ResultType.ERROR
    assert "not found" in result.error.lower()


@pytest.mark.asyncio
async def test_get_code_missing_file(get_code_action, mock_db_session):
    # Mock asset with non-existent path
    mock_asset = MagicMock(spec=Asset)
    mock_asset.id = 4
    mock_asset.asset_type = AssetType.GITHUB_FILE
    mock_asset.local_path = "/path/that/does/not/exist.sol"
    mock_asset.get_code.return_value = None  # Simulate file not found
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_asset

    # Execute action
    result = await get_code_action.execute("4")

    # Verify result
    assert result.type == ResultType.ERROR
    assert any(phrase in result.error.lower() for phrase in ["not found", "could not read"])  # Accept either error message


@pytest.mark.asyncio
async def test_get_code_invalid_asset_id(get_code_action):
    # Execute action with non-numeric ID
    result = await get_code_action.execute("not_a_number")

    # Verify result
    assert result.type == ResultType.ERROR
    assert "must be a number" in result.error.lower()
