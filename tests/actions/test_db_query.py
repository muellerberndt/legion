import pytest
from src.actions.db_query import DBQueryAction
import json
from unittest.mock import Mock, patch
from src.util.logging import Logger
from src.actions.base import BaseAction
from src.backend.database import DBSessionMixin

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
    # Create mocks for base class __init__ methods
    base_init = Mock(return_value=None)
    db_init = Mock(return_value=None)

    with (
        patch.object(BaseAction, "__init__", base_init),
        patch.object(DBSessionMixin, "__init__", db_init),
        patch.object(DBSessionMixin, "get_session", return_value=mock_session),
    ):

        action = DBQueryAction()
        action.logger = Mock()
        action.query_builder = mock_query_builder

        # Test valid query
        query_spec = {"from": "assets", "where": [{"field": "asset_type", "op": "=", "value": "github_file"}]}

        logger.info(f"Executing query with spec: {query_spec}")
        result = await action.execute(json.dumps(query_spec))
        logger.info(f"Got result: {result}")

        result_str = str(result)
        # Result should be a string containing CSV data
        assert "Found 1 results" in result_str
        assert "asset_type,id,source_url" in result_str  # Check CSV headers (alphabetically sorted)
        assert "github_file,test-id,https://github.com/test/repo" in result_str  # Check CSV data

        # Test invalid JSON
        result = await action.execute("invalid json")
        assert "Invalid query format" in str(result)

        # Test invalid query spec
        mock_query_builder.from_spec.side_effect = ValueError("Invalid query")
        result = await action.execute('{"invalid": "spec"}')
        assert "Error executing query" in str(result)

        # Reset mock for remaining tests
        mock_query_builder.from_spec.side_effect = None

        # Test query with no results
        mock_session.execute.return_value.all.return_value = []
        result = await action.execute(json.dumps(query_spec))
        assert "No results found." in str(result)

        # Test query with special characters
        result_row = Mock()
        mapping_dict = {"id": "test,id", "description": 'test"description', "list_field": ["item1", "item2"]}
        result_row._mapping = mapping_dict
        mock_session.execute.return_value.all.return_value = [result_row]

        result = await action.execute(json.dumps(query_spec))
        result_str = str(result)
        assert "Found 1 results" in result_str
        assert '"test,id"' in result_str  # Value with comma should be quoted
        assert '"test""description"' in result_str  # Quotes should be escaped
        assert '"[""item1"", ""item2""]"' in result_str  # Lists should be JSON-stringified and quoted
