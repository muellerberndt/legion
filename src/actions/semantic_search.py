from typing import List, Dict, Any
from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.backend.database import DBSessionMixin
from src.util.logging import Logger
from sqlalchemy import text
from openai import AsyncOpenAI
from src.config.config import Config

class SemanticSearchAction(BaseAction, DBSessionMixin):
    """Action to perform semantic search using embeddings"""
    
    spec = ActionSpec(
        name="semantic_search",
        description="Search assets using natural language",
        arguments=[
            ActionArgument(name="query", description="Natural language search query", required=True),
            ActionArgument(name="limit", description="Maximum number of results", required=False)
        ]
    )
    
    def __init__(self):
        super().__init__()
        DBSessionMixin.__init__(self)
        self.logger = Logger("SemanticSearch")
        self.config = Config()
        self.client = AsyncOpenAI(api_key=self.config.openai_api_key)
    
    def format_results(self, assets: List[Dict[str, Any]]) -> str:
        """Format search results for display"""
        if not assets:
            return "No matching assets found."
            
        lines = []
        for asset in assets:
            # Format project names
            project_names = asset.get('project_names', [])
            if None in project_names:
                project_names.remove(None)
            projects = ", ".join(project_names) if project_names else "No projects"
            
            # Format asset info
            lines.append(f"Asset: {asset['id']}")
            lines.append(f"Type: {asset['asset_type']}")
            lines.append(f"Projects: {projects}")
            if asset.get('source_url'):
                lines.append(f"Source: {asset['source_url']}")
            
            # Add any extra URLs from extra_data
            if asset.get('extra_data'):
                extra = asset['extra_data']
                if extra.get('file_url'):
                    lines.append(f"File: {extra['file_url']}")
                if extra.get('repo_url'):
                    lines.append(f"Repo: {extra['repo_url']}")
                if extra.get('explorer_url'):
                    lines.append(f"Explorer: {extra['explorer_url']}")
                    
            lines.append(f"Similarity: {asset['similarity']}%")
            lines.append("")  # Empty line between assets
            
        return "\n".join(lines)
    
    async def execute(self, query: str, limit: int = 10) -> str:
        """Execute semantic search"""
        try:
            # Get embedding for search query
            response = await self.client.embeddings.create(
                model="text-embedding-ada-002",
                input=query
            )
            query_embedding = response.data[0].embedding
            
            # Search using vector similarity
            with self.get_session() as session:
                # First check if we have any assets with embeddings
                check_query = text("SELECT COUNT(*) FROM assets WHERE embedding IS NOT NULL")
                count = session.execute(check_query).scalar()
                
                if count == 0:
                    return "No assets with embeddings found. Please ensure assets have been indexed with embeddings."
                
                # Format the embedding array for PostgreSQL
                embedding_array = '[' + ','.join(map(str, query_embedding)) + ']'
                
                # Perform similarity search using f-string for vector part
                sql = text(f"""
                    SELECT 
                        a.id,
                        a.asset_type,
                        a.file_url,
                        a.repo_url,
                        a.explorer_url,
                        a.extra_data,
                        array_agg(p.name) as project_names,
                        1 - (embedding::vector <=> '{embedding_array}'::vector) as similarity
                    FROM assets a
                    LEFT JOIN project_assets pa ON a.id = pa.asset_id
                    LEFT JOIN projects p ON pa.project_id = p.id
                    WHERE a.embedding IS NOT NULL
                    GROUP BY 
                        a.id,
                        a.asset_type,
                        a.file_url,
                        a.repo_url,
                        a.explorer_url,
                        a.embedding
                    ORDER BY embedding::vector <=> '{embedding_array}'::vector
                    LIMIT :limit
                """)
                
                result = session.execute(
                    sql,
                    {
                        'limit': limit
                    }
                )
                
                # Convert results to dictionaries and format them
                assets = []
                for row in result:
                    asset = dict(row._mapping)
                    # Format similarity score
                    asset['similarity'] = round(float(asset['similarity']) * 100, 2)
                    assets.append(asset)
                
                return self.format_results(assets)
                
        except Exception as e:
            self.logger.error(f"Semantic search failed: {str(e)}")
            raise