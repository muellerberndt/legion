from src.actions.base import BaseAction, ActionSpec, AsyncAction
from src.backend.database import DBSessionMixin
from src.util.logging import Logger
from src.models.base import Asset
from src.util.embeddings import update_asset_embedding
import asyncio

@AsyncAction
class GenerateEmbeddingsAction(BaseAction, DBSessionMixin):
    """Action to generate embeddings for all assets"""
    
    spec = ActionSpec(
        name="generate_embeddings",
        description="Generate vector embeddings for semantic search",
        arguments=[]
    )
    
    def __init__(self):
        super().__init__()
        DBSessionMixin.__init__(self)
        self.logger = Logger("GenerateEmbeddings")
    
    async def execute(self) -> str:
        """Execute the embedding generation"""
        try:
            with self.get_session() as session:
                # Get all assets that have local content but no embeddings
                assets = session.query(Asset).filter(
                    Asset.embedding.is_(None),
                    Asset.local_path.isnot(None)
                ).all()
                total_assets = len(assets)
                
                if not assets:
                    return "No assets found that need embeddings (must have local content)."
                
                self.logger.info(f"Generating embeddings for {total_assets} assets")
                
                # Process assets in batches to avoid rate limits
                batch_size = 10
                processed = 0
                skipped = 0
                
                for i in range(0, total_assets, batch_size):
                    batch = assets[i:i + batch_size]
                    
                    # Process each asset in the batch
                    for asset in batch:
                        try:
                            # Generate text from file contents
                            text = asset.generate_embedding_text()
                            if text:
                                await update_asset_embedding(asset)
                                processed += 1
                            else:
                                skipped += 1
                                self.logger.warning(f"No content found for asset {asset.id}")
                        except Exception as e:
                            skipped += 1
                            self.logger.error(f"Failed to process asset {asset.id}: {str(e)}")
                    
                    # Commit after each batch
                    session.commit()
                    
                    # Log progress
                    total_processed = processed + skipped
                    progress = (total_processed / total_assets) * 100
                    self.logger.info(
                        f"Progress: {progress:.1f}% "
                        f"({total_processed}/{total_assets} assets, "
                        f"{processed} successful, {skipped} skipped)"
                    )
                
                return (
                    f"Embedding generation complete:\n"
                    f"- {processed} assets processed successfully\n"
                    f"- {skipped} assets skipped (no content or errors)\n\n"
                    "You can now use semantic search to find similar assets!"
                )
                
        except Exception as e:
            self.logger.error(f"Failed to generate embeddings: {str(e)}")
            raise 