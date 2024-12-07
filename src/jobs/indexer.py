import asyncio
from src.jobs.base import Job, JobType, JobResult, JobStatus
from src.indexers.immunefi import ImmunefiIndexer
from src.backend.database import DBSessionMixin
import threading


class IndexerJob(Job, DBSessionMixin):
    """Job to run an indexer"""

    def __init__(self, platform: str, initialize_mode: bool = False):
        Job.__init__(self, JobType.INDEXER)
        DBSessionMixin.__init__(self)
        self.platform = platform
        self.initialize_mode = initialize_mode
        self._stop_event = threading.Event()
        self._executor = None
        self._task = None

    async def start(self) -> None:
        """Start the indexer"""
        try:
            self.status = JobStatus.RUNNING

            # Run the indexer directly in this event loop
            with self.get_session() as session:
                if self.platform == "immunefi":
                    indexer = ImmunefiIndexer(session=session, initialize_mode=self.initialize_mode)
                    # Pass stop event to indexer
                    indexer._stop_event = self._stop_event
                    await indexer.index()

                    self.status = JobStatus.COMPLETED
                    self.result = JobResult(success=True, message=f"Successfully indexed {self.platform}")
                else:
                    raise ValueError(f"Unknown platform: {self.platform}")

        except asyncio.CancelledError:
            self.logger.info("Indexer job cancelled")
            self.status = JobStatus.CANCELLED
            self.result = JobResult(success=False, message=f"Indexing of {self.platform} was cancelled")
            raise

        except Exception as e:
            self.logger.error(f"Failed to start indexer: {str(e)}")
            self.status = JobStatus.FAILED
            self.result = JobResult(success=False, message=f"Failed to start indexer: {str(e)}")
            raise

    async def stop(self) -> None:
        """Stop the indexer"""
        self.logger.info("Stopping indexer job...")
        self._stop_event.set()
