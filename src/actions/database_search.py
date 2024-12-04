from typing import List, Dict, Any, Optional
from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.backend.database import DBSessionMixin
from src.models.base import AssetType
from src.util.logging import Logger
from sqlalchemy import text

class DatabaseSearchAction(BaseAction, DBSessionMixin):
    """Action to search the database with structured filters"""
    
    spec = ActionSpec(
        name="database_search",
        description="""
Search projects and assets in the database.

Examples:
- Search assets: "search assets type=github_repo"
- Search projects: "search projects with_assets=true"
- Count results: "count assets type=deployed_contract"

Available filters for assets:
- type: One of [github_repo, github_file, deployed_contract]
- url: Searches across file_url, repo_url, and explorer_url
- project: Filter by project name

Available filters for projects:
- with_assets: Only show projects with assets
- type: Filter by project type (e.g. immunefi)
""",
        arguments=[
            ActionArgument(name="query", description="Search query with filters", required=True),
            ActionArgument(name="limit", description="Maximum number of results", required=False)
        ]
    )
    
    def __init__(self):
        super().__init__()
        DBSessionMixin.__init__(self)
        self.logger = Logger("DatabaseSearch")
        
    def _parse_filters(self, query: str) -> Dict[str, Any]:
        """Parse filters from query string"""
        filters = {}
        
        # Extract command type
        parts = query.lower().strip().split()
        if not parts:
            return filters
            
        # Get base command
        filters['command'] = parts[0]  # search/count
        if len(parts) > 1:
            filters['target'] = parts[1]  # assets/projects
            
        # Parse key=value filters
        for part in parts[2:]:
            if '=' in part:
                key, value = part.split('=', 1)
                # Handle boolean values
                if value.lower() == 'true':
                    value = True
                elif value.lower() == 'false':
                    value = False
                # Handle numeric values
                elif value.isdigit():
                    value = int(value)
                filters[key] = value
                
        return filters
    
    def _build_asset_query(self, filters: Dict[str, Any], count: bool = False) -> text:
        """Build asset query from filters"""
        select_clause = "COUNT(*)" if count else """
            a.id, 
            a.asset_type,
            a.file_url,
            a.repo_url,
            a.explorer_url,
            array_agg(p.name) as project_names
        """
        
        query = f"""
            SELECT {select_clause}
            FROM assets a
            LEFT JOIN project_assets pa ON a.id = pa.asset_id
            LEFT JOIN projects p ON pa.project_id = p.id
            WHERE 1=1
        """
        
        params = {}
        
        # Apply type filter
        if 'type' in filters:
            try:
                # Validate asset type
                asset_type = AssetType(filters['type'])
                query += " AND a.asset_type = :asset_type"
                params['asset_type'] = asset_type.value
            except ValueError:
                valid_types = [t.value for t in AssetType]
                raise ValueError(f"Invalid asset type. Must be one of: {valid_types}")
        
        # Apply URL filter
        if 'url' in filters:
            url = f"%{filters['url']}%"
            query += """ 
                AND (
                    a.file_url ILIKE :url OR 
                    a.repo_url ILIKE :url OR 
                    a.explorer_url ILIKE :url
                )
            """
            params['url'] = url
            
        # Apply project filter
        if 'project' in filters:
            project = f"%{filters['project']}%"
            query += " AND p.name ILIKE :project"
            params['project'] = project
            
        if not count:
            query += """
                GROUP BY 
                    a.id,
                    a.asset_type,
                    a.file_url,
                    a.repo_url,
                    a.explorer_url
                ORDER BY a.id
            """
            
        return text(query), params
    
    def _build_project_query(self, filters: Dict[str, Any], count: bool = False) -> text:
        """Build project query from filters"""
        select_clause = "COUNT(*)" if count else """
            p.id,
            p.name,
            p.description,
            p.project_type,
            COUNT(a.id) as asset_count
        """
        
        query = f"""
            SELECT {select_clause}
            FROM projects p
            LEFT JOIN project_assets pa ON p.id = pa.project_id
            LEFT JOIN assets a ON pa.asset_id = a.id
            WHERE 1=1
        """
        
        params = {}
        
        # Filter projects with assets
        if filters.get('with_assets'):
            query += " AND a.id IS NOT NULL"
            
        # Filter by project type
        if 'type' in filters:
            query += " AND p.project_type = :project_type"
            params['project_type'] = filters['type']
            
        if not count:
            query += """
                GROUP BY p.id, p.name, p.description, p.project_type
                ORDER BY p.name
            """
            
        return text(query), params
    
    def format_results(self, results: List[Dict[str, Any]], count: Optional[int] = None) -> str:
        """Format search results for display"""
        if count is not None:
            return f"Found {count} results"
            
        if not results:
            return "No results found."
            
        lines = [f"Found {len(results)} results:"]
        
        for item in results:
            if 'name' in item:  # Project
                lines.append(f"\nProject: {item['name']}")
                if item.get('description'):
                    lines.append(f"Description: {item['description']}")
                if item.get('project_type'):
                    lines.append(f"Type: {item['project_type']}")
                if 'asset_count' in item:
                    lines.append(f"Assets: {item['asset_count']}")
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
                # Format project names
                project_names = item.get('project_names', [])
                if project_names and None in project_names:
                    project_names.remove(None)
                if project_names:
                    lines.append(f"Projects: {', '.join(project_names)}")
                    
        return "\n".join(lines)
    
    async def execute(self, query: str, limit: int = 50) -> str:
        """Execute database search"""
        try:
            # Parse filters from query
            filters = self._parse_filters(query)
            
            # Get limit from filters or use default
            limit = filters.get('limit', limit)
            
            # Determine if this is a count query
            is_count = filters.get('command') == 'count'
            
            # Build appropriate query
            if filters.get('target') == 'projects':
                query, params = self._build_project_query(filters, is_count)
            else:  # Default to assets
                query, params = self._build_asset_query(filters, is_count)
            
            # Execute query
            with self.get_session() as session:
                result = session.execute(query, params)
                
                if is_count:
                    count = result.scalar()
                    return self.format_results([], count)
                else:
                    # Convert results to list of dicts
                    results = [dict(row._mapping) for row in result]
                    return self.format_results(results)
                
        except Exception as e:
            self.logger.error(f"Query failed: {str(e)}")
            raise 