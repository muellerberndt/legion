import pytest
from src.backend.query_builder import QueryBuilder
from src.models.base import Asset, Project
from src.models.event_log import EventLog
from sqlalchemy.sql.selectable import Select


def test_from_table():
    qb = QueryBuilder()
    qb.from_table("assets")
    assert qb._table == Asset

    qb = QueryBuilder()
    qb.from_table("projects")
    assert qb._table == Project

    qb = QueryBuilder()
    qb.from_table("event_logs")
    assert qb._table == EventLog

    with pytest.raises(ValueError, match="Access to table .* is not allowed"):
        qb.from_table("invalid")


def test_join():
    qb = QueryBuilder().from_table("assets")

    # Test valid join
    qb.join("projects", {"id": "id"})
    assert len(qb._joins) == 1
    assert qb._joins[0][0] == Project

    # Test join without from_table
    qb = QueryBuilder()
    with pytest.raises(ValueError, match="No base table selected"):
        qb.join("projects", {"id": "id"})

    # Test invalid join table
    qb = QueryBuilder().from_table("assets")
    with pytest.raises(ValueError, match="Access to table .* is not allowed"):
        qb.join("invalid", {"id": "id"})

    # Test invalid join field
    with pytest.raises(ValueError, match="Invalid join fields"):
        qb.join("projects", {"invalid_field": "id"})


def test_build():
    # Test complete query building
    qb = (
        QueryBuilder()
        .from_table("assets")
        .join("projects", {"id": "id"})
        .where("asset_type", "=", "github_file")
        .order_by("created_at", "desc")
        .limit(10)
    )

    query = qb.build()
    assert isinstance(query, Select)

    # Test building without table
    qb = QueryBuilder()
    with pytest.raises(ValueError, match="No table selected"):
        qb.build()


def test_query_spec():
    # Test complete specification
    spec = {
        "from": "assets",
        "join": {"table": "projects", "on": {"id": "id"}},
        "where": [{"field": "asset_type", "op": "=", "value": "github_file"}],
        "order_by": [{"field": "created_at", "direction": "desc"}],
        "limit": 10,
    }

    qb = QueryBuilder.from_spec(spec)
    query = qb.build()
    assert isinstance(query, Select)

    # Test minimal specification
    spec = {"from": "assets"}
    qb = QueryBuilder.from_spec(spec)
    query = qb.build()
    assert isinstance(query, Select)

    # Test invalid specifications
    with pytest.raises(ValueError, match="must include 'from' field"):
        QueryBuilder.from_spec({})

    with pytest.raises(ValueError, match="Access to table .* is not allowed"):
        QueryBuilder.from_spec({"from": "invalid"})

    with pytest.raises(ValueError, match="must include 'table' and 'on' fields"):
        QueryBuilder.from_spec({"from": "assets", "join": {"table": "projects"}})  # Missing 'on'
