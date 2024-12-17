from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.backend.query_builder import QueryBuilder
from src.backend.database import DBSessionMixin
from src.util.db_schema import get_db_query_hint
from src.util.logging import Logger
from src.actions.result import ActionResult
import json
from datetime import datetime


class DBQueryAction(BaseAction, DBSessionMixin):
    """Action to execute database queries"""

    spec = ActionSpec(
        name="db_query",
        description="Execute a database query using a JSON query specification",
        help_text="Query the database using a structured JSON format that supports filtering, joining, and sorting.",
        agent_hint=get_db_query_hint(),
        arguments=[ActionArgument(name="query", description="JSON string containing the query specification", required=True)],
    )

    def __init__(self):
        BaseAction.__init__(self)
        DBSessionMixin.__init__(self)
        self.logger = Logger("DBQueryAction")
        self.query_builder = QueryBuilder()

    def _serialize_value(self, value):
        """Helper to serialize values to JSON-compatible format"""
        if hasattr(value, "__table__"):
            # Handle SQLAlchemy models
            model_dict = {}
            for column in value.__table__.columns:
                model_dict[column.name] = self._serialize_value(getattr(value, column.name))
            return model_dict
        elif isinstance(value, datetime):
            return value.isoformat()
        else:
            return value

    async def execute(self, query: str) -> ActionResult:
        """Execute a database query"""
        try:
            # Parse query specification
            try:
                query_spec = json.loads(query)
            except json.JSONDecodeError:
                return ActionResult.error("Invalid query format - must be valid JSON")

            # Build and execute query
            try:
                query_builder = self.query_builder.from_spec(query_spec)
                query = query_builder.build()  # Build the SQLAlchemy query
                with self.get_session() as session:
                    results = []
                    columns = set()  # Track all columns for table headers

                    # First pass: collect all possible columns
                    for row in session.execute(query).all():
                        if hasattr(row, "_mapping"):
                            # Handle SQLAlchemy Result rows
                            result = {}
                            for key in row._mapping.keys():
                                value = row._mapping.get(key)
                                # Handle nested objects (e.g. Project.name -> project_name)
                                if hasattr(value, "__table__"):
                                    for col in value.__table__.columns:
                                        col_name = f"{value.__table__.name.lower()}_{col.name}"
                                        result[col_name] = self._serialize_value(getattr(value, col.name))
                                        columns.add(col_name)
                                else:
                                    result[key] = self._serialize_value(value)
                                    columns.add(key)
                            results.append(result)
                        else:
                            # Handle SQLAlchemy model objects
                            result = self._serialize_value(row)
                            columns.update(result.keys())
                            results.append(result)

                    # Format results
                    total_count = len(results)
                    if total_count == 0:
                        return ActionResult.text("No results found.")

                    # Convert results to CSV format
                    headers = sorted(list(columns))  # Sort columns for consistent order
                    csv_lines = [",".join(headers)]  # Header row

                    for result in results:
                        row = []
                        for header in headers:
                            value = result.get(header)
                            # Format special values
                            if isinstance(value, (list, dict)):
                                value = json.dumps(value).replace('"', '""')  # Escape quotes for CSV
                            elif value is None:
                                value = ""
                            else:
                                value = str(value).replace('"', '""')  # Escape quotes for CSV
                            # Quote the value if it contains commas, quotes, or newlines
                            if any(c in str(value) for c in ',""\n\r'):
                                value = f'"{value}"'
                            row.append(value)
                        csv_lines.append(",".join(row))

                    # Add summary to metadata
                    metadata = {"summary": f"Found {total_count} results", "total": total_count}

                    return ActionResult.text(f"{metadata['summary']}\n\n```\n{chr(10).join(csv_lines)}\n```")

            except Exception as e:
                self.logger.error(f"Error executing query: {str(e)}")
                return ActionResult.error(f"Error executing query: {str(e)}")

        except Exception as e:
            self.logger.error(f"Query execution failed: {str(e)}")
            return ActionResult.error(f"Query execution failed: {str(e)}")
