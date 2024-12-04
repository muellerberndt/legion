import pytest
from src.actions.db_query import DBQueryAction
import json
from unittest.mock import Mock, patch

@pytest.fixture
def mock_session():
    with patch('src.backend.database.DBSessionMixin.get_session') as mock:
        session = Mock()
        session.__enter__ = Mock(return_value=session)
        session.__exit__ = Mock(return_value=None)
        
        # Mock query results
        result_row = Mock()
        result_row._asdict.return_value = {
            "id": "test-id",
            "asset_type": "github_file",
            "source_url": "https://github.com/test/repo"
        }
        session.execute.return_value.all.return_value = [result_row]
        
        mock.return_value = session
        yield session

@pytest.mark.asyncio
async def test_db_query_action(mock_session):
    action = DBQueryAction()
    
    # Test valid query
    query_spec = {
        "from": "assets",
        "where": [
            {"field": "asset_type", "op": "=", "value": "github_file"}
        ]
    }
    
    result = await action.execute(json.dumps(query_spec))
    result_data = json.loads(result)
    
    assert result_data["count"] == 1
    assert len(result_data["results"]) == 1
    assert result_data["results"][0]["asset_type"] == "github_file"
    
    # Test invalid JSON
    result = await action.execute("invalid json")
    assert "Error: Invalid JSON" in result
    
    # Test invalid query spec
    result = await action.execute('{"invalid": "spec"}')
    assert "Error building query" in result
    
    # Test query with no results
    mock_session.execute.return_value.all.return_value = []
    result = await action.execute(json.dumps(query_spec))
    result_data = json.loads(result)
    assert result_data["count"] == 0
    assert len(result_data["results"]) == 0
    
    # Test query with many results
    many_results = [Mock() for _ in range(150)]
    for r in many_results:
        r._asdict.return_value = {"id": "test"}
    mock_session.execute.return_value.all.return_value = many_results
    
    result = await action.execute(json.dumps(query_spec))
    result_data = json.loads(result)
    assert result_data["count"] == 150
    assert len(result_data["results"]) == 100  # Limited to 100
    assert "note" in result_data  # Should have note about limited results 