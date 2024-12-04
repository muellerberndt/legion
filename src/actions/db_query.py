from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.backend.query_builder import QueryBuilder
from src.backend.database import DBSessionMixin
import json
from datetime import datetime
from src.util.logging import Logger

class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder for datetime objects"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

class DBQueryAction(BaseAction, DBSessionMixin):
    """Action to perform database queries using the QueryBuilder"""
    
    spec = ActionSpec(
        name="db_query",
        description="Execute database queries using a JSON query specification. Example: db_query '{\"from\": \"assets\", \"where\": [{\"field\": \"asset_type\", \"op\": \"=\", \"value\": \"github_file\"}]}'",
        arguments=[
            ActionArgument(
                name="query_spec",
                description="JSON query specification. See QueryBuilder documentation for format.",
                required=True
            )
        ]
    )
    
    def __init__(self):
        super().__init__()
        DBSessionMixin.__init__(self)
        self.logger = Logger("DBQueryAction")
        
    async def execute(self, query_spec: str) -> str:
        """Execute the database query action"""
        try:
            # Parse query specification
            try:
                spec = json.loads(query_spec)
            except json.JSONDecodeError:
                return "Error: Invalid JSON query specification"
                
            # Build and execute query
            try:
                query = QueryBuilder.from_spec(spec).build()
            except ValueError as e:
                return f"Error building query: {str(e)}"
                
            # Execute query
            with self.get_session() as session:
                results = session.execute(query).all()
                
            # Format results
            formatted_results = []
            for row in results:
                if hasattr(row, "_mapping"):  # SQLAlchemy 1.4+ result rows
                    result_dict = dict(row._mapping)
                    # Convert any SQLAlchemy objects in the result
                    for key, value in result_dict.items():
                        if hasattr(value, "__table__"):  # SQLAlchemy model object
                            result_dict[key] = {
                                col.name: getattr(value, col.name)
                                for col in value.__table__.columns
                            }
                    formatted_results.append(result_dict)
                elif hasattr(row, "__table__"):  # SQLAlchemy model object
                    result_dict = {}
                    for column in row.__table__.columns:
                        value = getattr(row, column.name)
                        result_dict[column.name] = value
                    formatted_results.append(result_dict)
                else:  # Regular tuple
                    formatted_results.append(tuple(str(value) for value in row))
                    
            # Build response
            response = {
                "count": len(formatted_results),
                "results": formatted_results[:100]  # Limit to first 100 results
            }
            
            if len(formatted_results) > 100:
                response["note"] = f"Showing first 100 of {len(formatted_results)} results"
                
            return json.dumps(response, indent=2, cls=DateTimeEncoder)
            
        except Exception as e:
            self.logger.error(f"Error executing query: {str(e)}")
            return f"Error executing query: {str(e)}"
            
    @classmethod
    def example(cls) -> str:
        """Return example usage"""
        return """
        # Example queries:
        
        # Find all GitHub files in a project:
        db_query '{
            "from": "assets",
            "join": {
                "table": "projects",
                "on": {"id": "id"}
            },
            "select": ["assets.id", "assets.source_url", "projects.name"],
            "where": [
                {"field": "assets.asset_type", "op": "=", "value": "github_file"},
                {"field": "projects.name", "op": "=", "value": "specific-project"}
            ],
            "limit": 10
        }'
        
        # Search for assets by keyword:
        db_query '{
            "from": "assets",
            "where": [
                {"field": "source_url", "op": "like", "value": "github.com"}
            ],
            "order_by": [
                {"field": "created_at", "direction": "desc"}
            ]
        }'
        """ 