import asyncio
from src.jobs.base import Job, JobType, JobResult, JobStatus
from src.indexers.immunefi import ImmunefiIndexer
from src.backend.database import DBSessionMixin
import threading
import concurrent.futures

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
            
            # Create a new thread pool executor
            self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            
            # Run the indexer in a separate thread with its own event loop
            # Don't wait for completion - let it run in background
            self._task = asyncio.create_task(self._run_in_thread())
            
            # Add a callback to handle completion
            self._task.add_done_callback(self._on_task_complete)
            
        except Exception as e:
            self.logger.error(f"Failed to start indexer: {str(e)}")
            self.status = JobStatus.FAILED
            self.result = JobResult(
                success=False,
                message=f"Failed to start indexer: {str(e)}"
            )
            if self._executor:
                self._executor.shutdown(wait=False)
                self._executor = None
                
    def _on_task_complete(self, task):
        """Handle task completion"""
        try:
            # Get the result (will raise exception if task failed)
            task.result()
            
            if self._stop_event.is_set():
                self.status = JobStatus.CANCELLED
                self.result = JobResult(
                    success=False,
                    message=f"Indexing of {self.platform} was cancelled"
                )
            else:
                self.status = JobStatus.COMPLETED
                self.result = JobResult(
                    success=True,
                    message=f"Successfully indexed {self.platform}"
                )
                
        except Exception as e:
            self.logger.error(f"Indexer task failed: {str(e)}")
            self.status = JobStatus.FAILED
            self.result = JobResult(
                success=False,
                message=f"Indexing failed: {str(e)}"
            )
        finally:
            if self._executor:
                self._executor.shutdown(wait=False)
                self._executor = None
            
    async def _run_in_thread(self) -> None:
        """Run the indexer in a separate thread with its own event loop"""
        try:
            # Run the indexer in a separate thread
            loop = asyncio.new_event_loop()
            await asyncio.get_event_loop().run_in_executor(
                self._executor,
                self._run_indexer,
                loop
            )
                
        except Exception as e:
            self.logger.error(f"Indexer thread failed: {str(e)}")
            raise
            
    def _run_indexer(self, loop):
        """Run the indexer in a new event loop"""
        asyncio.set_event_loop(loop)
        
        try:
            with self.get_session() as session:
                if self.platform == "immunefi":
                    indexer = ImmunefiIndexer(
                        session=session, 
                        initialize_mode=self.initialize_mode
                    )
                    # Pass stop event to indexer
                    indexer._stop_event = self._stop_event
                    loop.run_until_complete(indexer.index())
                    
        except Exception as e:
            self.logger.error(f"Error in indexer thread: {str(e)}")
            raise
        finally:
            loop.close()
            
    async def stop(self) -> None:
        """Stop the indexer"""
        self.logger.info("Stopping indexer job...")
        self._stop_event.set()
        
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None