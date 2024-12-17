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
                    for row in session.execute(query).all():
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
                        return ActionResult.text("No results found.")

                    # Format results with summary line
                    summary = f"Found {total_count} results"
                    if total_count > 100:
                        summary += " (Showing first 100)"
                        results = results[:100]

                    # Return as formatted text with JSON data
                    result_text = summary + ":\n" + json.dumps(results, indent=2)
                    return ActionResult.text(result_text)

            except Exception as e:
                self.logger.error(f"Error executing query: {str(e)}")
                return ActionResult.error(f"Error executing query: {str(e)}")

        except Exception as e:
            self.logger.error(f"Query execution failed: {str(e)}")
            return ActionResult.error(f"Query execution failed: {str(e)}")
