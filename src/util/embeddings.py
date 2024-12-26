from sentence_transformers import SentenceTransformer
from src.models.base import Asset
from typing import List, Dict
import numpy as np
import logging
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.config.config import Config


class EmbeddingGenerator:
    """Handles generation of embeddings using sentence-transformers"""

    _instance = None
    _model = None
    _config = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if self._config is None:
            self._config = Config()

        if self._model is None:
            model_name = self._config.embeddings_model
            logging.info(f"Initializing embedding model: {model_name}")
            self._model = SentenceTransformer(model_name)

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using configured model"""
        # Convert text to embedding
        embedding = self._model.encode(text, convert_to_tensor=False)
        return embedding.tolist()


async def generate_embedding(text: str) -> List[float]:
    """Generate embedding for text"""
    generator = EmbeddingGenerator.get_instance()
    return generator.generate_embedding(text)


async def generate_file_embeddings(files: List[Dict[str, str]]) -> List[float]:
    """Generate and combine embeddings for multiple files

    Args:
        files: List of dicts with 'name' and 'content' keys

    Returns:
        Combined embedding vector
    """
    # Generate embeddings for each file
    embeddings = []
    for file_info in files:
        try:
            # Create context-aware content with special tokens for code
            content = f"[FILE] {file_info['name']} [CONTENT] {file_info['content']}"
            embedding = await generate_embedding(content)
            embeddings.append(embedding)
        except Exception as e:
            logging.error(f"Failed to generate embedding for {file_info['name']}: {str(e)}")
            continue

    if not embeddings:
        return []

    # Combine embeddings by averaging
    # This preserves the dimensionality while capturing overall semantics
    combined = np.mean(embeddings, axis=0)
    return combined.tolist()


def update_embedding_raw(session: Session, asset_id: str, embedding: List[float]) -> None:
    """Update embedding directly using raw SQL to ensure correct type conversion"""
    logging.info(f"Updating embedding for asset {asset_id}")

    # Convert numpy arrays to lists if needed
    if isinstance(embedding, np.ndarray):
        embedding = embedding.tolist()

    # Convert to string format that pgvector expects
    embedding_str = f"[{','.join(str(x) for x in embedding)}]"

    # Update using direct assignment
    try:
        result = session.execute(
            text("UPDATE assets SET embedding = :embedding::vector WHERE id = :id"),
            {"id": asset_id, "embedding": embedding_str},
        )
        logging.info(f"Update result: {result.rowcount} rows affected")
    except Exception as e:
        # Log and re-raise any errors
        logging.error(f"Failed to update embedding for asset {asset_id}: {str(e)}")
        raise


async def update_asset_embedding(asset: Asset) -> List[float]:
    """Generate embedding for an asset"""
    logger = logging.getLogger()
    logger.info(f"Generating embedding for asset {asset.id}")

    try:
        # Generate embedding
        text = asset.generate_embedding_text()
        if not text:  # Add check for empty text
            raise ValueError("No text content available for embedding")

        embedding = await generate_embedding(text)
        return embedding

    except Exception as e:
        logger.error(f"Failed to generate embedding for asset {asset.id}: {str(e)}")
        raise
