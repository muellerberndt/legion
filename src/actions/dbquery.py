from typing import List, Dict, Any
from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.backend.database import DBSessionMixin
from src.backend.query import SQLQueryBuilder
from src.util.logging import Logger

class DBQueryAction(BaseAction, DBSessionMixin):
    """Action to query the database"""
    
    spec = ActionSpec(
        name="query",
        description="Query the database",
        arguments=[
            ActionArgument(name="query", description="Natural language query", required=True),
            ActionArgument(name="limit", description="Maximum number of results", required=False)
        ]
    )
    
    def __init__(self):
        super().__init__()
        DBSessionMixin.__init__(self)
        self.logger = Logger("DBQuery")
        
    def format_results(self, results: List[Dict[str, Any]], count: int) -> str:
        """Format query results for display"""
        if not results:
            return "No results found."
            
        lines = [f"Found {count} total results:"]
        
        for item in results:
            # Handle both projects and assets
            if 'name' in item:  # Project
                lines.append(f"\nProject: {item['name']}")
                if item.get('description'):
                    lines.append(f"Description: {item['description']}")
                if item.get('project_type'):
                    lines.append(f"Type: {item['project_type']}")
            else:  # Asset
                lines.append(f"\nAsset: {item['id']}")
                if item.get('asset_type'):
                    lines.append(f"Type: {item['asset_type']}")
                if item.get('file_url'):
                    lines.append(f"File: {item['file_url']}")
                if item.get('repo_url'):
                    lines.append(f"Repo: {item['repo_url']}")
                if item.get('explorer_url'):
                    lines.append(f"Explorer: {item['explorer_url']}")
                    
        return "\n".join(lines)
    
    async def execute(self, query: str, limit: int = 10) -> str:
        """Execute database query"""
        try:
            # Build and execute query
            builder = SQLQueryBuilder()
            sql_query = builder.build_query(query)
            
            with self.get_session() as session:
                result = session.execute(sql_query)
                rows = [dict(row._mapping) for row in result]
                
                # Get total count
                count_query = builder.build_count_query(query)
                count_result = session.execute(count_query)
                total_count = count_result.scalar()
                
                # Format results
                return self.format_results(rows[:limit], total_count)
                
        except Exception as e:
            self.logger.error(f"Query failed: {str(e)}")
            raise 