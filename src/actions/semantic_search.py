from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.backend.database import DBSessionMixin
from src.util.embeddings import generate_embedding
from sqlalchemy import text


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
- Smart contract code and patterns
- Documentation and comments
- Function signatures and names
- Project descriptions and metadata

Examples:
/semantic_search "Find contracts that handle token swaps"
/semantic_search "Show me implementations of reentrancy guards"
/semantic_search "Find code related to access control"
/semantic_search "Solidity contracts with interest calculation"

Results are ranked by semantic similarity to your query.""",
        agent_hint=(
            "Use this command when you want to find code or assets based on concepts and meaning rather than exact text matches. "
            "Great for finding implementations of specific patterns or concepts."
        ),
        arguments=[ActionArgument(name="query", description="Natural language search query", required=True)],
    )

    def __init__(self):
        DBSessionMixin.__init__(self)

    async def execute(self, query: str) -> str:
        """Execute semantic search

        Args:
            query: Natural language search query

        Returns:
            Formatted string containing search results
        """
        try:
            # Add context markers to query for better matching with stored embeddings
            enhanced_query = f"[QUERY] {query}"
            embedding = await generate_embedding(enhanced_query)

            # Search for similar assets
            with self.get_session() as session:
                # Use pgvector's L2 distance operator for similarity search
                sql = text(
                    f"""
                    SELECT
                        a.id,
                        a.asset_type,
                        a.source_url,
                        a.local_path,
                        a.extra_data,
                        a.created_at,
                        a.updated_at,
                        p.name as project_name,
                        p.description as project_description,
                        1 / (1 + (a.embedding <-> array[{','.join(map(str, embedding))}]::vector(384))) as similarity
                    FROM assets a
                    LEFT JOIN project_assets pa ON a.id = pa.asset_id
                    LEFT JOIN projects p ON pa.project_id = p.id
                    WHERE a.embedding IS NOT NULL
                    ORDER BY a.embedding <-> array[{','.join(map(str, embedding))}]::vector(384)
                    LIMIT 10
                    """
                )

                results = []
                for row in session.execute(sql):
                    # Get URLs from extra_data
                    extra_data = row.extra_data or {}

                    # Format result with more context
                    result = {
                        "id": row.id,
                        "asset_type": row.asset_type,
                        "url": (
                            row.source_url
                            or extra_data.get("file_url")
                            or extra_data.get("repo_url")
                            or extra_data.get("explorer_url")
                        ),
                        "project": row.project_name or "Unknown Project",
                        "description": row.project_description,
                        "similarity": float(row.similarity),
                    }

                    # Add local file preview if available
                    if row.local_path and row.asset_type == "deployed_contract":
                        try:
                            import os

                            for root, _, files in os.walk(row.local_path):
                                sol_files = [f for f in files if f.endswith(".sol")]
                                if sol_files:
                                    result["files"] = sol_files
                                    break
                        except Exception:
                            pass  # Skip file preview on error

                    results.append(result)

                # Format results as readable message
                if results:
                    message = [f"🔍 Search results for: {query}\n"]
                    for i, r in enumerate(results, 1):
                        similarity_pct = int(r["similarity"] * 100)
                        message.extend(
                            [f"{i}. {r['project']} ({similarity_pct}% match)", f"Type: {r['asset_type']}", f"URL: {r['url']}"]
                        )
                        if r.get("files"):
                            message.append(f"Files: {', '.join(r['files'])}")
                        if r.get("description"):
                            message.append(f"Description: {r['description']}")
                        message.append("")  # Empty line between results

                    return "\n".join(message)
                else:
                    return "No matching results found."

        except Exception as e:
            return f"Search failed: {str(e)}"
