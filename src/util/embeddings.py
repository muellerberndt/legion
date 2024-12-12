from sentence_transformers import SentenceTransformer
from src.models.base import Asset
from typing import List, Dict
import os
import numpy as np
import logging
from sqlalchemy import text
from sqlalchemy.orm import Session, object_session


class EmbeddingGenerator:
    """Handles generation of embeddings using sentence-transformers"""

    _instance = None
    _model = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if self._model is None:
            # Use a small but effective model for semantic similarity
            self._model = SentenceTransformer("all-MiniLM-L6-v2")

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using sentence-transformers"""
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


async def update_asset_embedding(asset: Asset) -> None:
    """Update embedding for an asset"""
    try:
        # Get session from asset
        session = object_session(asset)
        if session is None:
            raise ValueError("Asset is not attached to a session")

        # Generate text representation
        if asset.asset_type == "deployed_contract":
            # For deployed contracts, process each file separately
            files = []
            if os.path.isdir(asset.local_path):
                for root, _, filenames in os.walk(asset.local_path):
                    for filename in sorted(filenames):
                        if not filename.endswith(".sol"):  # Only process Solidity files
                            continue
                        file_path = os.path.join(root, filename)
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                content = f.read()
                                files.append({"name": filename, "content": content})
                        except UnicodeDecodeError:
                            # Skip binary files
                            continue

            if files:
                embedding = await generate_file_embeddings(files)
                update_embedding_raw(session, asset.id, embedding)

        else:
            # For single files or repos, use the combined text
            text = asset.generate_embedding_text()
            if text:
                # Add context markers for better semantic understanding
                text = f"[TYPE] {asset.asset_type} [CONTENT] {text}"
                embedding = await generate_embedding(text)
                update_embedding_raw(session, asset.id, embedding)

    except Exception as e:
        logging.error(f"Failed to update embedding for asset {asset.id}: {str(e)}")
        # Re-raise all errors to let the job handle them
        raise
