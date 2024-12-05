"""Job manager for handling background jobs"""

import asyncio
from typing import Dict, List, Type
from src.jobs.base import Job, JobStatus
from src.util.logging import Logger
from src.backend.database import DBSessionMixin
from src.models.job import JobRecord
from datetime import datetime

class JobManager(DBSessionMixin):
    """Manages all running jobs"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(JobManager, cls).__new__(cls)
            cls._instance.initialize()
        return cls._instance
    
    def initialize(self):
        """Initialize the job manager"""
        self.logger = Logger("JobManager")
        self._jobs: Dict[str, Job] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._running = False
        
    async def start(self) -> None:
        """Start the job manager"""
        if self._running:
            return
            
        self.logger.info("Starting job manager")
        self._running = True
        
        # Clean up any stale jobs from previous runs
        self._jobs.clear()
        self._tasks.clear()
        
    async def stop(self) -> None:
        """Stop all running jobs"""
        if not self._running:
            return
            
        self.logger.info("Stopping job manager")
        
        # Cancel all running tasks
        for job_id, task in list(self._tasks.items()):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    self.logger.error(f"Error cancelling task {job_id}: {e}")
                finally:
                    if job_id in self._tasks:
                        del self._tasks[job_id]
                
        # Stop all jobs
        for job_id, job in list(self._jobs.items()):
            try:
                self.logger.info(f"Stopping job: {job_id}")
                await job.stop()
            except Exception as e:
                self.logger.error(f"Failed to stop job {job_id}: {e}")
            finally:
                if job_id in self._jobs:
                    del self._jobs[job_id]
            
        self._running = False
        
    async def stop_job(self, job_id: str) -> bool:
        """Stop a specific job
        
        Args:
            job_id: ID of the job to stop
            
        Returns:
            True if job was stopped, False if job not found
        """
        job = self._jobs.get(job_id)
        if not job:
            self.logger.warning(f"Job {job_id} not found")
            return False
            
        try:
            # Import here to avoid circular imports
            from src.jobs.notification import JobNotifier
            
            self.logger.info(f"Stopping job {job_id}")
            
            # Cancel the task if it exists
            if job_id in self._tasks:
                task = self._tasks[job_id]
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        self.logger.error(f"Error cancelling task {job_id}: {e}")
                    finally:
                        if job_id in self._tasks:
                            del self._tasks[job_id]
            
            # Stop the job
            await job.stop()
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.utcnow()
            
            # Update job record in database
            with self.get_session() as session:
                job_record = session.query(JobRecord).filter(JobRecord.id == job_id).first()
                if job_record:
                    job_record.status = JobStatus.CANCELLED.value
                    job_record.completed_at = job.completed_at
                    session.commit()
            
            # Send cancellation notification
            notifier = JobNotifier()
            await notifier.notify_completion(
                job_id=job.id,
                job_type=job.type.value,
                status=JobStatus.CANCELLED.value,
                message="Job cancelled by user",
                started_at=job.started_at,
                completed_at=job.completed_at
            )
            
            # Clean up job from memory
            if job_id in self._jobs:
                del self._jobs[job_id]
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop job {job_id}: {e}")
            # Ensure cleanup even on error
            if job_id in self._jobs:
                del self._jobs[job_id]
            if job_id in self._tasks:
                del self._tasks[job_id]
            return False
            
    def get_job(self, name: str) -> Job:
        """Get a registered job by name"""
        return self._jobs.get(name)
        
    def list_jobs(self, job_type: Type[Job] = None) -> List[Dict]:
        """List all registered jobs
        
        Args:
            job_type: Optional job type to filter by
            
        Returns:
            List of job dictionaries
        """
        jobs = []
        for job in self._jobs.values():
            if job_type and job.type != job_type:
                continue
            jobs.append(job.to_dict())
        return jobs
        
    async def submit_job(self, job: Job) -> str:
        """Submit a new job for execution
        
        Args:
            job: The job to submit
            
        Returns:
            The job ID
        """
        if not self._running:
            raise RuntimeError("Job manager is not running")
            
        try:
            # Create database record and register job in a single transaction
            with self.get_session() as session:
                # Create and register job record
                job_record = JobRecord(
                    id=job.id,
                    type=job.type.value,
                    status=job.status.value,
                    created_at=datetime.utcnow()
                )
                session.add(job_record)
                
                # Register job in memory
                if job.id in self._jobs:
                    self.logger.warning(f"Job {job.id} already registered")
                    return job.id
                    
                self._jobs[job.id] = job
                self.logger.info(f"Registered job: {job.id}")
                
                # Create background task for job
                task = asyncio.create_task(self._run_job(job))
                self._tasks[job.id] = task
                
                # Add task cleanup callback
                task.add_done_callback(self._create_task_done_callback(job.id))
                
                # Commit the initial record
                session.commit()
            
            return job.id
            
        except Exception as e:
            self.logger.error(f"Failed to submit job: {str(e)}")
            # Clean up registration if start failed
            if job.id in self._jobs:
                del self._jobs[job.id]
            if job.id in self._tasks:
                del self._tasks[job.id]
            raise
            
    def _create_task_done_callback(self, job_id: str):
        """Create a callback for task completion that properly handles the event loop
        
        Args:
            job_id: ID of the job
            
        Returns:
            Callback function
        """
        def callback(task):
            try:
                # Get task exception if any
                if task.cancelled():
                    self.logger.info(f"Task for job {job_id} was cancelled")
                elif task.exception():
                    self.logger.error(f"Task for job {job_id} failed with error: {task.exception()}")
                    
                # Only clean up task, keep job in memory
                if job_id in self._tasks:
                    del self._tasks[job_id]
                    
            except Exception as e:
                self.logger.error(f"Error in task completion callback for job {job_id}: {e}")
        return callback
        
    async def _run_job(self, job: Job) -> None:
        """Run a job and handle its completion
        
        Args:
            job: The job to run
        """
        try:
            # Import here to avoid circular imports
            from src.jobs.notification import JobNotifier
            
            # Start the job
            job.status = JobStatus.RUNNING
            job.started_at = datetime.utcnow()
            await job.start()
            
            # If job completed successfully
            if job.status != JobStatus.FAILED:
                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.utcnow()
            
            # Update record with completion status
            with self.get_session() as session:
                job_record = session.query(JobRecord).filter(JobRecord.id == job.id).first()
                if job_record:
                    job_record.status = job.status.value
                    job_record.started_at = job.started_at
                    job_record.completed_at = job.completed_at
                    job_record.error = job.error
                    if job.result:
                        job_record.success = job.result.success
                        job_record.message = job.result.message
                        job_record.data = job.result.data
                        job_record.outputs = job.result.outputs
                    session.commit()
            
            # Send completion notification
            notifier = JobNotifier()
            await notifier.notify_completion(
                job_id=job.id,
                job_type=job.type.value,
                status=job.status.value,
                message=job.result.message if job.result else None,
                outputs=job.result.outputs if job.result else None,
                data=job.result.data if job.result else None,
                error=job.error,
                started_at=job.started_at,
                completed_at=job.completed_at
            )
            
        except asyncio.CancelledError:
            self.logger.info(f"Job {job.id} was cancelled")
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.utcnow()
            raise
            
        except Exception as e:
            self.logger.error(f"Error running job {job.id}: {e}")
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.utcnow()
            
            # Update record with error status
            with self.get_session() as session:
                job_record = session.query(JobRecord).filter(JobRecord.id == job.id).first()
                if job_record:
                    job_record.status = JobStatus.FAILED.value
                    job_record.started_at = job.started_at
                    job_record.completed_at = job.completed_at
                    job_record.error = str(e)
                    session.commit()
                    
            # Send failure notification
            try:
                notifier = JobNotifier()
                await notifier.notify_completion(
                    job_id=job.id,
                    job_type=job.type.value,
                    status=JobStatus.FAILED.value,
                    message=str(e),
                    error=str(e),
                    started_at=job.started_at,
                    completed_at=job.completed_at
                )
            except Exception as notify_error:
                self.logger.error(f"Failed to send failure notification for job {job.id}: {notify_error}")
        
    async def _notify_completion(self, job) -> None:
        """Send notification about job completion"""
        try:
            await self.notifier.notify_completion(
                job_id=job.id,
                job_type=job.type.value,
                status=job.status.value,
                message=job.result.message if job.result else None,
                outputs=job.result.outputs if job.result else None,
                data=job.result.data if job.result else None,
                error=job.error,
                started_at=job.started_at,
                completed_at=job.completed_at
            )
        except Exception as e:
            self.logger.error(f"Failed to send job completion notification: {e}")