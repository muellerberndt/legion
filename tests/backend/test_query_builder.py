import pytest
from src.backend.query_builder import QueryBuilder
from src.models.base import Asset, Project
from sqlalchemy import select
from sqlalchemy.sql.selectable import Select

def test_from_table():
    qb = QueryBuilder()
    qb.from_table("assets")
    assert qb._table == Asset
    
    qb = QueryBuilder()
    qb.from_table("projects")
    assert qb._table == Project
    
    with pytest.raises(ValueError, match="Invalid table name"):
        qb.from_table("invalid")

def test_join():
    qb = QueryBuilder().from_table("assets")
    
    # Test valid join using the project_assets association table
    qb.join("projects", {"id": "id"})  # Join through the association table
    assert len(qb._joins) == 1
    assert qb._joins[0][0] == Project
    
    # Test join without from_table
    qb = QueryBuilder()
    with pytest.raises(ValueError, match="No base table selected"):
        qb.join("projects", {"id": "id"})
        
    # Test invalid join table
    qb = QueryBuilder().from_table("assets")
    with pytest.raises(ValueError, match="Invalid table name"):
        qb.join("invalid", {"id": "id"})
        
    # Test invalid join field
    with pytest.raises(ValueError, match="Field invalid_field does not exist"):
        qb.join("projects", {"invalid_field": "id"})

def test_select():
    qb = QueryBuilder().from_table("assets")
    
    # Test valid field selection
    qb.select("assets.id", "assets.source_url")
    assert len(qb._selected_fields) == 2
    
    # Test invalid field format
    with pytest.raises(ValueError, match="Invalid field format"):
        qb.select("invalid_format")
        
    # Test invalid table
    with pytest.raises(ValueError, match="Invalid table name"):
        qb.select("invalid.field")
        
    # Test invalid field
    with pytest.raises(ValueError, match="Field invalid_field does not exist"):
        qb.select("assets.invalid_field")

def test_where():
    qb = QueryBuilder().from_table("assets")
    
    # Test basic operators
    qb.where("asset_type", "=", "github_file")
    qb.where("source_url", "like", "github.com")
    
    # Test table.field format
    qb.where("assets.asset_type", "=", "github_file")
    qb.where("projects.name", "like", "test")
    
    # Test invalid field
    with pytest.raises(ValueError, match="Invalid field"):
        qb.where("invalid_field", "=", "value")
        
    # Test invalid operator
    with pytest.raises(ValueError, match="Invalid operator"):
        qb.where("asset_type", "invalid", "value")

def test_order_by():
    qb = QueryBuilder().from_table("assets")
    
    # Test ascending
    qb.order_by("created_at", "asc")
    assert len(qb._order_by) == 1
    
    # Test descending
    qb.order_by("updated_at", "desc")
    assert len(qb._order_by) == 2
    
    # Test table.field format
    qb.order_by("assets.created_at", "desc")
    qb.order_by("projects.name", "asc")
    
    # Test invalid field
    with pytest.raises(ValueError, match="Invalid field"):
        qb.order_by("invalid_field")
        
    # Test invalid direction
    with pytest.raises(ValueError, match="Direction must be either"):
        qb.order_by("created_at", "invalid")

def test_limit_offset():
    qb = QueryBuilder().from_table("assets")
    
    # Test valid limit
    qb.limit(10)
    assert qb._limit == 10
    
    # Test valid offset
    qb.offset(20)
    assert qb._offset == 20
    
    # Test invalid limit
    with pytest.raises(ValueError, match="Limit must be a positive integer"):
        qb.limit(-1)
        
    # Test invalid offset
    with pytest.raises(ValueError, match="Offset must be a positive integer"):
        qb.offset(-1)

def test_build():
    # Test complete query building
    qb = (QueryBuilder()
        .from_table("assets")
        .join("projects", {"id": "id"})
        .select("assets.id", "assets.source_url", "projects.name")
        .where("projects.project_type", "=", "github")
        .where("assets.asset_type", "=", "github_file")
        .order_by("assets.created_at", "desc")
        .limit(10)
        .offset(0)
    )
    
    query = qb.build()
    assert isinstance(query, Select)
    
    # Test building without table
    qb = QueryBuilder()
    with pytest.raises(ValueError, match="No table selected"):
        qb.build()

def test_complex_conditions():
    qb = QueryBuilder().from_table("assets")
    
    # Test IN operator
    qb.where("asset_type", "in", ["github_file", "github_dir"])
    
    # Test IS NULL
    qb.where("extra_data", "is null", None)
    
    # Test LIKE with special characters
    qb.where("source_url", "like", "github.com/user-name/repo-name")
    
    query = qb.build()
    assert isinstance(query, Select)

def test_query_string():
    qb = (QueryBuilder()
        .from_table("assets")
        .join("projects", {"id": "id"})
        .select("assets.id", "projects.name")
        .where("projects.project_type", "=", "github")
        .limit(10)
    )
    
    # Test string representation
    query_str = str(qb)
    assert "SELECT" in query_str
    assert "JOIN projects" in query_str
    assert "WHERE" in query_str
    assert "LIMIT 10" in query_str

def test_query_spec():
    # Test complete specification
    spec = {
        "from": "assets",
        "join": {
            "table": "projects",
            "on": {"id": "id"}
        },
        "select": ["assets.id", "projects.name"],
        "where": [
            {"field": "assets.asset_type", "op": "=", "value": "github_file"},
            {"field": "projects.project_type", "op": "=", "value": "github"}
        ],
        "order_by": [
            {"field": "assets.created_at", "direction": "desc"}
        ],
        "limit": 10
    }
    
    qb = QueryBuilder.from_spec(spec)
    query = qb.build()
    assert isinstance(query, Select)
    
    # Test minimal specification
    spec = {
        "from": "assets"
    }
    qb = QueryBuilder.from_spec(spec)
    query = qb.build()
    assert isinstance(query, Select)
    
    # Test invalid specifications
    with pytest.raises(ValueError, match="must include 'from' field"):
        QueryBuilder.from_spec({})
        
    with pytest.raises(ValueError, match="Invalid table name"):
        QueryBuilder.from_spec({"from": "invalid"})
        
    with pytest.raises(ValueError, match="must include 'table' and 'on' fields"):
        QueryBuilder.from_spec({
            "from": "assets",
            "join": {"table": "projects"}  # Missing 'on'
        })
        
    with pytest.raises(ValueError, match="must be a list of fields"):
        QueryBuilder.from_spec({
            "from": "assets",
            "select": "assets.id"  # Should be a list
        })
        
    with pytest.raises(ValueError, match="must be a list of conditions"):
        QueryBuilder.from_spec({
            "from": "assets",
            "where": {"field": "id", "op": "=", "value": 1}  # Should be a list
        }) 