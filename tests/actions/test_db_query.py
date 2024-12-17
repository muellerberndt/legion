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
        result_row._mapping = mapping_dict

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

    # Result should be a string containing JSON data
    assert "Found 1 results:" in result
    assert "test-id" in result
    assert "github_file" in result
    assert "https://github.com/test/repo" in result

    # Test invalid JSON
    result = await action.execute("invalid json")
    assert "Invalid query format" in result

    # Test invalid query spec
    mock_query_builder.from_spec.side_effect = ValueError("Invalid query")
    result = await action.execute('{"invalid": "spec"}')
    assert "Error executing query" in result

    # Reset mock for remaining tests
    mock_query_builder.from_spec.side_effect = None

    # Test query with no results
    mock_session.execute.return_value.all.return_value = []
    result = await action.execute(json.dumps(query_spec))
    assert "No results found." in result

    # Test query with many results
    many_results = []
    for i in range(150):
        row = Mock()
        mapping_dict = {"id": f"test-{i}"}
        row._mapping = mapping_dict
        many_results.append(row)

    mock_session.execute.return_value.all.return_value = many_results

    result = await action.execute(json.dumps(query_spec))
    assert "Found 150 results:" in result
    assert "(Showing first 100" in result
