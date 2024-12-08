from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.util.embeddings import generate_embedding
from src.util.logging import Logger
import json


class EmbeddingsAction(BaseAction):
    """Action to generate embeddings for text"""

    spec = ActionSpec(
        name="embeddings",
        description="Generate embeddings for text input",
        help_text="""Generate vector embeddings for semantic search

Usage:
/embeddings <text>

This command generates vector embeddings that can be used for:
- Semantic search
- Text similarity comparison
- Natural language processing

The embeddings are generated using OpenAI's text-embedding model.
Returns a JSON object with the embedding vector.

Example:
/embeddings "Check for reentrancy vulnerabilities"
""",
        agent_hint="Use this command when you need to generate vector embeddings for text to enable semantic search or similarity comparison",
        arguments=[ActionArgument(name="text", description="Text to generate embeddings for", required=True)],
    )

    def __init__(self):
        self.logger = Logger("EmbeddingsAction")

    async def execute(self, text: str) -> str:
        """Generate embeddings for text"""
        try:
            embedding = await generate_embedding(text)
            return json.dumps({"text": text, "embedding": embedding})

        except Exception as e:
            self.logger.error(f"Failed to generate embeddings: {str(e)}")
            return json.dumps({"error": f"Failed to generate embeddings: {str(e)}"})
