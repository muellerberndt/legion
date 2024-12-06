from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.backend.query_builder import QueryBuilder
from src.util.logging import Logger
from src.backend.database import DBSessionMixin
import json

class DBQueryAction(BaseAction, DBSessionMixin):
    """Action to execute database queries"""
    
    spec = ActionSpec(
        name="db_query",
        description="Execute a database query",
        help_text="""Execute a database query using a JSON query specification.

Usage:
/db_query <query_spec>

The query_spec should be a JSON object with the following structure:
{
    "from": "table_name",
    "where": [
        {"field": "column", "op": "=", "value": "value"}
    ],
    "order_by": "column",
    "limit": 100
}

Examples:
/db_query {"from": "assets", "where": [{"field": "asset_type", "op": "=", "value": "github_repo"}]}
/db_query {"from": "projects", "order_by": "name"}""",
        agent_hint="Use this command when you need to query the database for specific information. The query builder supports basic SQL operations.",
        arguments=[
            ActionArgument(name="query", description="JSON query specification", required=True)
        ]
    )
    
    def __init__(self):
        BaseAction.__init__(self)
        DBSessionMixin.__init__(self)
        self.logger = Logger("DBQueryAction")
        self.query_builder = QueryBuilder()
        
    async def execute(self, query_spec: str) -> str:
        """Execute a database query
        
        Args:
            query_spec: JSON string containing query specification
            
        Returns:
            JSON string containing query results
        """
        try:
            # Parse query spec
            try:
                spec = json.loads(query_spec)
            except json.JSONDecodeError:
                return json.dumps({
                    "error": "Invalid JSON query specification"
                })
                
            # Build and execute query
            try:
                query = self.query_builder.build_query(spec)
                results = []
                
                with self.get_session() as session:
                    rows = session.execute(query).all()
                    for row in rows:
                        # Convert row to dict
                        result = {}
                        for key in row._mapping.keys():
                            result[key] = row._mapping.get(key)
                        results.append(result)
                        
                # Limit results and add note if truncated
                total_count = len(results)
                if total_count > 100:
                    results = results[:100]
                    return json.dumps({
                        "count": total_count,
                        "results": results,
                        "note": f"Results truncated to 100 of {total_count} total matches"
                    })
                    
                return json.dumps({
                    "count": total_count,
                    "results": results
                })
                
            except Exception as e:
                return json.dumps({
                    "error": f"Error building query: {str(e)}"
                })
                
        except Exception as e:
            self.logger.error(f"Query execution failed: {str(e)}")
            return json.dumps({
                "error": f"Query execution failed: {str(e)}"
            }) 