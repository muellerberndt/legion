from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.backend.query_builder import QueryBuilder
from src.backend.database import DBSessionMixin
from src.util.db_schema import get_db_query_hint
from src.util.logging import Logger
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
            # Convert datetime to ISO format string
            return value.isoformat()
        return value

    async def execute(self, query: str) -> str:
        """Execute a database query using the query builder format.

        Args:
            query: JSON string containing the query specification

        Returns:
            Formatted string containing query results
        """
        try:
            # Parse query spec
            try:
                spec = json.loads(query)
            except json.JSONDecodeError:
                return '❌ Invalid query format. Query must be a valid JSON string.\n\nExample:\n```\n{\n  "from": "projects",\n  "where": [\n    {\n      "field": "name",\n      "op": "ilike",\n      "value": "test"\n    }\n  ]\n}\n```'

            # Build and execute query
            try:
                # Build the query
                query = self.query_builder.from_spec(spec).build()

                # Execute with session
                with self.get_session() as session:
                    rows = session.execute(query).all()

                    # Convert results to list of dicts
                    results = []
                    for row in rows:
                        if hasattr(row, "_mapping"):
                            # Handle SQLAlchemy Result rows
                            result = {}
                            for key in row._mapping.keys():
                                result[key] = self._serialize_value(row._mapping.get(key))
                            results.append(result)
                        else:
                            # Handle SQLAlchemy model objects
                            results.append(self._serialize_value(row))

                    # Format results
                    total_count = len(results)
                    if total_count == 0:
                        return "No results found."

                    lines = [f"📊 Found {total_count} results:"]

                    # Add truncation note if needed
                    if total_count > 100:
                        results = results[:100]
                        lines.append(f"(Showing first 100 of {total_count} results)\n")

                    # Format each result
                    for i, result in enumerate(results, 1):
                        lines.append(f"\n{i}. {json.dumps(result, indent=2)}")

                    return "\n".join(lines)

            except Exception as e:
                self.logger.error(f"Error executing query: {str(e)}")
                return f"❌ Error executing query: {str(e)}"

        except Exception as e:
            self.logger.error(f"Query execution failed: {str(e)}")
            return f"❌ Query execution failed: {str(e)}"
