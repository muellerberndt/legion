"""Job for generating embeddings for assets"""

from src.jobs.base import Job, JobResult
from src.backend.database import DBSessionMixin
from src.models.base import Asset
from src.util.embeddings import update_asset_embedding
from src.util.logging import Logger
from sqlalchemy import select
from datetime import datetime


class EmbedJob(Job, DBSessionMixin):
    """Job to generate embeddings for all assets in the database"""

    BATCH_SIZE = 10  # Commit every 10 assets

    def __init__(self):
        Job.__init__(self, "embed")
        DBSessionMixin.__init__(self)
        self.logger = Logger("EmbedJob")
        self.processed = 0
        self.failed = 0
        self._commit_count = 0  # Track number of commits

    async def start(self) -> None:
        """Start the embedding job"""
        try:
            self.started_at = datetime.utcnow()
            self.logger.info("Starting embedding generation for all assets")

            with self.get_session() as session:
                # Get all assets
                query = select(Asset)
                assets = session.execute(query).scalars().all()
                total = len(assets)
                self.logger.info(f"Found {total} assets to process")

                # Process assets in batches
                current_batch = []
                for i, asset in enumerate(assets):
                    try:
                        self.logger.info(f"Processing asset {asset.id} ({i+1}/{total})")
                        await update_asset_embedding(asset)
                        self.processed += 1
                        current_batch.append(asset.id)

                        # Only commit on full batch or last asset
                        should_commit = len(current_batch) >= self.BATCH_SIZE or i == total - 1
                        if should_commit and current_batch:  # Only commit if we have assets to commit
                            self.logger.info(f"Committing batch of {len(current_batch)} assets: {current_batch}")
                            try:
                                session.commit()
                                self._commit_count += 1
                                self.logger.info(f"Commit #{self._commit_count} successful")
                                current_batch = []  # Clear batch after successful commit
                            except Exception as e:
                                self.logger.error(f"Failed to commit batch: {str(e)}")
                                session.rollback()
                                raise  # Re-raise the commit error

                    except Exception as e:
                        self.failed += 1
                        self.logger.error(f"Failed to generate embedding for asset {asset.id}: {str(e)}")
                        if "Database error" in str(e):
                            session.rollback()
                            raise  # Re-raise database errors immediately
                        # For non-database errors, continue with next asset
                        session.rollback()  # Rollback any changes from the failed asset

            # Create result with success/failure stats
            result = JobResult(
                success=self.failed == 0,  # Only successful if no failures
                message=f"Generated embeddings for {self.processed} assets ({self.failed} failed)",
                data={"processed": self.processed, "failed": self.failed, "commits": self._commit_count},
            )

            # Add detailed output
            if self.failed > 0:
                result.add_output(f"⚠️ {self.failed} assets failed to process")
            result.add_output(f"✅ Successfully processed {self.processed} assets")
            result.add_output(f"💾 Completed {self._commit_count} database commits")

            await self.complete(result)

        except Exception as e:
            self.logger.error(f"Embedding job failed: {str(e)}")
            await self.fail(str(e))

    async def stop_handler(self) -> None:
        """Handle job stop request"""
        self.logger.info("Stopping embedding job")
        # No special cleanup needed for embedding job
