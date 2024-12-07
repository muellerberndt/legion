import pytest
from src.actions.db_query import DBQueryAction
import json
from unittest.mock import Mock, patch, MagicMock
from src.util.logging import Logger

logger = Logger("TestDBQuery")


@pytest.fixture
def mock_session():
    with patch("src.backend.database.DBSessionMixin.get_session") as mock:
        session = Mock()
        session.__enter__ = Mock(return_value=session)
        session.__exit__ = Mock(return_value=None)

        # Mock query results with proper _mapping attribute
        result_row = Mock()
        mapping_dict = {"id": "test-id", "asset_type": "github_file", "source_url": "https://github.com/test/repo"}
        # Create a MagicMock that behaves like a dict
        mapping = MagicMock()
        mapping.__getitem__.side_effect = mapping_dict.__getitem__
        mapping.keys.return_value = mapping_dict.keys()
        mapping.items.return_value = mapping_dict.items()
        mapping.get.side_effect = mapping_dict.get
        result_row._mapping = mapping

        session.execute.return_value.all.return_value = [result_row]

        mock.return_value = session
        yield session


@pytest.fixture
def mock_query_builder():
    with patch("src.actions.db_query.QueryBuilder") as mock:
        builder = Mock()
        # Mock the builder to return itself for method chaining
        builder.from_spec = Mock(return_value=builder)
        builder.build = Mock(return_value="SELECT * FROM assets")
        mock.return_value = builder
        yield builder


@pytest.mark.asyncio
async def test_db_query_action(mock_session, mock_query_builder):
    action = DBQueryAction()

    # Test valid query
    query_spec = {"from": "assets", "where": [{"field": "asset_type", "op": "=", "value": "github_file"}]}

    logger.info(f"Executing query with spec: {query_spec}")
    result = await action.execute(json.dumps(query_spec))
    logger.info(f"Got result: {result}")

    if not result:
        logger.error("Result is empty!")
        raise ValueError("Empty result from action")

    result_data = json.loads(result)

    assert "count" in result_data
    assert "results" in result_data
    assert result_data["count"] == 1
    assert len(result_data["results"]) == 1
    assert result_data["results"][0]["asset_type"] == "github_file"

    # Test invalid JSON
    result = await action.execute("invalid json")
    result_data = json.loads(result)
    assert "error" in result_data
    assert "Invalid JSON" in result_data["error"]

    # Test invalid query spec
    mock_query_builder.from_spec.side_effect = ValueError("Invalid query")
    result = await action.execute('{"invalid": "spec"}')
    result_data = json.loads(result)
    assert "error" in result_data
    assert "Invalid query" in result_data["error"]

    # Reset mock for remaining tests
    mock_query_builder.from_spec.side_effect = None

    # Test query with no results
    mock_session.execute.return_value.all.return_value = []
    result = await action.execute(json.dumps(query_spec))
    result_data = json.loads(result)
    assert result_data["count"] == 0
    assert len(result_data["results"]) == 0

    # Test query with many results
    many_results = []
    for i in range(150):
        row = Mock()
        mapping_dict = {"id": f"test-{i}"}
        # Create a MagicMock that behaves like a dict
        mapping = MagicMock()
        mapping.__getitem__.side_effect = mapping_dict.__getitem__
        mapping.keys.return_value = mapping_dict.keys()
        mapping.items.return_value = mapping_dict.items()
        mapping.get.side_effect = mapping_dict.get
        row._mapping = mapping
        many_results.append(row)

    mock_session.execute.return_value.all.return_value = many_results

    result = await action.execute(json.dumps(query_spec))
    result_data = json.loads(result)
    assert result_data["count"] == 150
    assert len(result_data["results"]) == 100  # Limited to 100
    assert "note" in result_data  # Should have note about limited results
