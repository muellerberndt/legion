from sqlalchemy import inspect
from src.backend.database import db

# Define allowed tables
ALLOWED_TABLES = {"projects", "assets"}


def get_table_schema() -> str:
    """Get a formatted string describing the database schema.

    Returns:
        A string containing table and column information suitable for agent hints.
    """
    inspector = inspect(db.get_engine())

    schema_parts = []

    # Get all tables but only process allowed ones
    for table_name in inspector.get_table_names():
        if table_name not in ALLOWED_TABLES:
            continue

        columns = inspector.get_columns(table_name)
        primary_key = inspector.get_pk_constraint(table_name)
        foreign_keys = inspector.get_foreign_keys(table_name)

        # Format table info
        table_info = [f"Table: {table_name}"]

        # Add columns
        table_info.append("Columns:")
        for col in columns:
            nullable = "NULL" if col["nullable"] else "NOT NULL"
            pk = " PRIMARY KEY" if col["name"] in primary_key["constrained_columns"] else ""
            table_info.append(f"  - {col['name']}: {col['type']} {nullable}{pk}")

        # Add foreign keys if any
        if foreign_keys:
            table_info.append("Foreign Keys:")
            for fk in foreign_keys:
                referred_table = fk["referred_table"]
                constrained_cols = ", ".join(fk["constrained_columns"])
                referred_cols = ", ".join(fk["referred_columns"])
                table_info.append(f"  - {constrained_cols} -> {referred_table}({referred_cols})")

        schema_parts.append("\n".join(table_info))

    return "\n\n".join(schema_parts)


def get_db_query_hint() -> str:
    """Get a formatted hint for the db_query command.

    Returns:
        A string containing the schema and example queries.
    """
    schema = get_table_schema()

    field_descriptions = """
Field Descriptions:
- project_type: "bounty" or "contest"
- project_source: E.g. "immunefi" or "code4rena"
- keywords: Array of tags that describe the project e.g. ["Solidity", "DeFi"]
- asset_type: Type of asset ("github_repo", "github_file", "deployed_contract")
- identifier: Unique identifier for the asset (usually the URL)
"""

    examples = """
Example Queries:
- List recent projects:
  db_query '{"from": "projects", "order_by": [{"field": "created_at", "direction": "desc"}], "limit": 10}'

- Get assets for a specific project:
  db_query '{"from": "assets", "where": [{"field": "project_id", "op": "=", "value": 123}]}'

- Find projects with specific keywords:
  db_query '{"from": "projects", "where": [{"field": "keywords", "op": "@>", "value": ["Solidity"]}]}'

- Get GitHub repositories for Immunefi projects:
  db_query '{"from": "assets", "join": {"table": "projects", "on": {"project_id": "id"}}, "where": [{"field": "projects.project_source", "op": "=", "value": "immunefi"}, {"field": "assets.asset_type", "op": "=", "value": "github_repo"}]}'
"""

    return f"""Database Schema:
{schema}

{field_descriptions}

{examples}

First argument must be a JSON string containing the query specification in quotes.

The following tables are accessible: {', '.join(sorted(ALLOWED_TABLES))}.

Query format:
- "from": Required. One of: {', '.join(sorted(ALLOWED_TABLES))}
- "select": Optional. List of column names to return
- "where": Optional. List of conditions with format: {{"field": "column_name", "op": "operator", "value": "value"}}
  - Operators: "=", "!=", ">", "<", ">=", "<=", "like", "ilike", "in", "not in", "is null", "is not null", "@>" (array contains)
- "join": Optional. Join specification with format: {{"table": "table_name", "on": {{"field1": "field2"}}}}
- "order_by": Optional. List of sort specifications with format: {{"field": "column_name", "direction": "asc|desc"}}
- "limit": Optional. Number of results to return
- "offset": Optional. Number of results to skip
"""
