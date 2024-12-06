from typing import List, Dict, Any
from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.backend.database import DBSessionMixin
from src.models.base import Asset
from src.util.embeddings import generate_embedding
from sqlalchemy import text
import json

class SemanticSearchAction(BaseAction, DBSessionMixin):
    """Action to perform semantic search over assets"""
    
    spec = ActionSpec(
        name="semantic_search",
        description="Search assets using natural language",
        help_text="""Perform semantic search over assets using natural language.

Usage:
/semantic_search <query>

This command uses AI embeddings to find assets that are semantically similar to your query.
The search looks at:
- Code content and patterns
- Documentation and comments
- File and project descriptions

Examples:
/semantic_search "Find contracts that handle token swaps"
/semantic_search "Show me implementations of reentrancy guards"
/semantic_search "Find code related to access control"

Results are ranked by semantic similarity to your query.""",
        agent_hint="Use this command when you want to find code or assets based on concepts and meaning rather than exact text matches. Great for finding implementations of specific patterns or concepts.",
        arguments=[
            ActionArgument(
                name="query",
                description="Natural language search query",
                required=True
            )
        ]
    )
    
    def __init__(self):
        DBSessionMixin.__init__(self)
        
    async def execute(self, query: str) -> str:
        """Execute semantic search
        
        Args:
            query: Natural language search query
            
        Returns:
            JSON string containing search results
        """
        try:
            # Generate embedding for query
            embedding = await generate_embedding(query)
            
            # Search for similar assets
            with self.get_session() as session:
                # Use vector similarity search
                sql = text("""
                    SELECT 
                        a.id,
                        a.asset_type,
                        a.source_url,
                        a.file_url,
                        a.repo_url,
                        a.explorer_url,
                        1 - (a.embedding <=> :embedding) as similarity
                    FROM assets a
                    WHERE a.embedding IS NOT NULL
                    ORDER BY a.embedding <=> :embedding
                    LIMIT 10
                """)
                
                results = []
                for row in session.execute(sql, {"embedding": embedding}):
                    result = {
                        "id": row.id,
                        "asset_type": row.asset_type,
                        "url": row.source_url or row.file_url or row.repo_url or row.explorer_url,
                        "similarity": float(row.similarity)
                    }
                    results.append(result)
                    
                return json.dumps({
                    "query": query,
                    "results": results
                })
                
        except Exception as e:
            return json.dumps({
                "error": f"Search failed: {str(e)}",
                "query": query
            })