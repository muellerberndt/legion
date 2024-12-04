from openai import AsyncOpenAI
from src.config.config import Config
from src.models.base import Asset
from typing import List, Dict
import asyncio
import os
import numpy as np
import logging

async def generate_embedding(text: str) -> List[float]:
    """Generate embedding for text using OpenAI API"""
    config = Config()
    client = AsyncOpenAI(api_key=config.openai_api_key)
    
    response = await client.embeddings.create(
        model="text-embedding-ada-002",
        input=text
    )
    return response.data[0].embedding

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
            # Create context-aware content
            content = f"File: {file_info['name']}\n\n{file_info['content']}"
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

async def update_asset_embedding(asset: Asset) -> None:
    """Update embedding for an asset"""
    # Generate text representation
    if asset.asset_type == "deployed_contract":
        # For deployed contracts, process each file separately
        files = []
        if os.path.isdir(asset.local_path):
            for root, _, filenames in os.walk(asset.local_path):
                for filename in sorted(filenames):
                    file_path = os.path.join(root, filename)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            files.append({
                                'name': filename,
                                'content': content
                            })
                    except UnicodeDecodeError:
                        # Skip binary files
                        continue
                        
        if files:
            embedding = await generate_file_embeddings(files)
            asset.embedding = embedding
            
    else:
        # For single files or repos, use the combined text
        text = asset.generate_embedding_text()
        if text:
            embedding = await generate_embedding(text)
            asset.embedding = embedding