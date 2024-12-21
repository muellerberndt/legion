"""Job manager for handling background jobs"""

import asyncio
from typing import Dict, List, Type, Optional, Any
from src.jobs.base import Job, JobStatus
from src.util.logging import Logger
from src.backend.database import DBSessionMixin
from src.models.job import JobRecord
from datetime import datetime, timedelta
import time


class JobManager(DBSessionMixin):
    """Manages all running jobs"""

    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(JobManager, cls).__new__(cls)
            cls._instance.initialize()
        return cls._instance

    @classmethod
    async def get_instance(cls) -> "JobManager":
        """Get or create the singleton instance"""
        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def initialize(self):
        """Initialize the job manager"""
        self.logger = Logger("JobManager")
        self._running_jobs: Dict[str, Job] = {}  # Jobs in memory
        self._tasks: Dict[str, asyncio.Task] = {}
        self._running = False

    async def start(self) -> None:
        """Start the job manager"""
        if self._running:
            return

        self.logger.info("Starting job manager")
        self._running = True

        # Clean up any stale jobs from previous runs
        self._running_jobs.clear()
        self._tasks.clear()

    async def stop(self) -> None:
        """Stop all running jobs and clean up"""
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

        # Mark any remaining running jobs as failed
        for job in list(self._running_jobs.values()):
            try:
                with self.get_session() as session:
                    job_record = JobRecord(
                        id=job.id,
                        type=job.type,
                        status=JobStatus.FAILED.value,
                        started_at=job.started_at,
                        completed_at=datetime.utcnow(),
                        success=False,
                        message="Job terminated due to server shutdown",
                    )
                    session.add(job_record)
                    session.commit()
            except Exception as e:
                self.logger.error(f"Error storing terminated job {job.id}: {e}")

        self._running_jobs.clear()
        self._tasks.clear()
        self._running = False

    async def stop_job(self, job_id: str) -> bool:
        """Stop a specific job

        Args:
            job_id: ID of the job to stop

        Returns:
            True if job was stopped, False if job not found
        """
        job = self._running_jobs.get(job_id)
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
                job_type=job.type,
                status=JobStatus.CANCELLED.value,
                message="Job cancelled by user",
                started_at=job.started_at,
                completed_at=job.completed_at,
            )

            # Clean up job from memory
            if job_id in self._running_jobs:
                del self._running_jobs[job_id]

            return True

        except Exception as e:
            self.logger.error(f"Failed to stop job {job_id}: {e}")
            # Ensure cleanup even on error
            if job_id in self._running_jobs:
                del self._running_jobs[job_id]
            if job_id in self._tasks:
                del self._tasks[job_id]
            return False

    async def delete_job(self, job_id: str) -> bool:
        """Delete a job and its database record

        Args:
            job_id: ID of the job to delete

        Returns:
            True if job was deleted, False if job not found
        """
        try:
            # Stop the job first if it's running
            if job_id in self._running_jobs:
                await self.stop_job(job_id)

            # Delete the database record
            with self.get_session() as session:
                job_record = session.query(JobRecord).filter(JobRecord.id == job_id).first()
                if job_record:
                    session.delete(job_record)
                    session.commit()
                    self.logger.info(f"Deleted job record for {job_id}")
                    return True
                else:
                    self.logger.warning(f"No database record found for job {job_id}")
                    return False

        except Exception as e:
            self.logger.error(f"Failed to delete job {job_id}: {e}")
            return False

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID

        Args:
            job_id: ID of the job to get

        Returns:
            The job if found, None otherwise
        """
        return self._running_jobs.get(job_id)

    def get_most_recent_finished_job(self) -> Optional[JobRecord]:
        """Get the most recently finished job from the database.

        Returns:
            The most recent finished job record if found, None otherwise
        """
        try:
            with self.get_session() as session:
                # Query for the most recent completed, failed, or cancelled job
                job = (
                    session.query(JobRecord)
                    .filter(
                        JobRecord.status.in_([JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value])
                    )
                    .order_by(JobRecord.completed_at.desc(), JobRecord.started_at.desc())
                    .first()
                )
                return job
        except Exception as e:
            self.logger.error(f"Failed to get most recent job: {e}")
            return None

    async def list_jobs(self, job_type: Type[Job] = None, status: Optional[JobStatus] = None) -> List[Dict]:
        """List jobs with optional type and status filters"""
        try:
            # Get running jobs from memory
            running_jobs = []
            if status in (None, JobStatus.RUNNING):
                running_jobs = [
                    {
                        "id": job.id,
                        "type": job.type,
                        "status": JobStatus.RUNNING.value,
                        "started_at": job.started_at.isoformat() if job.started_at else None,
                        "completed_at": None,
                        "success": None,
                        "message": None,
                        "outputs": job.result.outputs[:3] if job.result and job.result.outputs else [],
                    }
                    for job in self._running_jobs.values()
                    if not job_type or job.type == job_type
                ]

            # Get completed jobs from database (last 24 hours)
            completed_jobs = []
            if status != JobStatus.RUNNING:
                with self.get_session() as session:
                    # Calculate cutoff time (24 hours ago)
                    cutoff_time = datetime.utcnow() - timedelta(hours=24)

                    query = session.query(JobRecord)
                    if job_type:
                        query = query.filter(JobRecord.type == job_type)

                    # Add time filter
                    query = query.filter(JobRecord.completed_at >= cutoff_time)

                    # Order by most recent first
                    query = query.order_by(JobRecord.created_at.desc())

                    records = query.all()
                    completed_jobs = [
                        {
                            "id": job.id,
                            "type": job.type,
                            "status": job.status,
                            "started_at": job.started_at.isoformat() if job.started_at else None,
                            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                            "success": job.success,
                            "message": job.message,
                            "outputs": job.outputs[:3] if job.outputs else [],
                        }
                        for job in records
                    ]

            # Combine and sort by started_at
            all_jobs = running_jobs + completed_jobs
            return sorted(all_jobs, key=lambda x: x["started_at"] or "", reverse=True)

        except Exception as e:
            self.logger.error(f"Error listing jobs: {e}")
            return []

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
                    type=job.type,
                    status=job.status.value,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    success=None,
                    message=None,
                    data=None,
                    outputs=[],
                )
                session.add(job_record)

                # Register job in memory
                if job.id in self._running_jobs:
                    self.logger.warning(f"Job {job.id} already registered")
                    return job.id

                self._running_jobs[job.id] = job
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
            if job.id in self._running_jobs:
                del self._running_jobs[job.id]
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

                # Clean up task
                if job_id in self._tasks:
                    del self._tasks[job_id]

            except Exception as e:
                self.logger.error(f"Error in task completion callback for job {job_id}: {e}")

        return callback

    async def _run_job(self, job: Job) -> None:
        """Run a job and handle its lifecycle"""
        try:
            # Start the job
            job.status = JobStatus.RUNNING
            job.started_at = datetime.utcnow()
            await job.start()

            # Job completed successfully
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()

            # Store completed job in database
            with self.get_session() as session:
                job_record = session.query(JobRecord).filter(JobRecord.id == job.id).first()
                if job_record:
                    job_record.status = job.status.value
                    job_record.started_at = job.started_at
                    job_record.completed_at = job.completed_at
                    job_record.success = job.result.success if job.result else None
                    job_record.message = job.result.message if job.result else None
                    job_record.data = job.result.data if job.result else None
                    job_record.outputs = job.result.outputs if job.result else []
                    session.commit()

            # Send completion notification
            try:
                from src.jobs.notification import JobNotifier

                notifier = JobNotifier()
                await notifier.notify_completion(
                    job_id=job.id,
                    job_type=job.type,
                    status=job.status.value,
                    message=job.result.message if job.result else None,
                    outputs=job.result.outputs if job.result else None,
                    data=job.result.data if job.result else None,
                    started_at=job.started_at,
                    completed_at=job.completed_at,
                )
            except Exception as e:
                self.logger.error(f"Failed to send completion notification: {e}")

        except asyncio.CancelledError:
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.utcnow()

            # Store cancelled job
            with self.get_session() as session:
                job_record = session.query(JobRecord).filter(JobRecord.id == job.id).first()
                if job_record:
                    job_record.status = job.status.value
                    job_record.started_at = job.started_at
                    job_record.completed_at = job.completed_at
                    session.commit()
            raise

        except Exception as e:
            error_msg = str(e)
            job.status = JobStatus.FAILED
            job.completed_at = datetime.utcnow()

            # Store failed job
            with self.get_session() as session:
                job_record = session.query(JobRecord).filter(JobRecord.id == job.id).first()
                if job_record:
                    job_record.status = job.status.value
                    job_record.started_at = job.started_at
                    job_record.completed_at = job.completed_at
                    job_record.success = False
                    job_record.message = error_msg
                    session.commit()

            # Send failure notification
            try:
                from src.jobs.notification import JobNotifier

                notifier = JobNotifier()
                await notifier.notify_completion(
                    job_id=job.id,
                    job_type=job.type,
                    status=job.status.value,
                    message=error_msg,
                    started_at=job.started_at,
                    completed_at=job.completed_at,
                )
            except Exception as notify_error:
                self.logger.error(f"Failed to send failure notification: {notify_error}")

        finally:
            # Clean up memory
            if job.id in self._running_jobs:
                del self._running_jobs[job.id]

    async def _notify_completion(self, job) -> None:
        """Send notification about job completion"""
        try:
            status_emoji = {JobStatus.COMPLETED.value: "✅", JobStatus.FAILED.value: "❌", JobStatus.CANCELLED.value: "⚠️"}.get(
                job.status.value, "ℹ️"
            )

            message = f"{status_emoji} Job {job.id} ({job.type}) {job.status.value}.\nUse /job_result {job.id} to view results"

            await self.notifier.notify_completion(
                job_id=job.id,
                job_type=job.type,
                status=job.status.value,
                message=message,
                # Don't include outputs/data in notification
                outputs=None,
                data=None,
                started_at=job.started_at,
                completed_at=job.completed_at,
            )
        except Exception as e:
            self.logger.error(f"Failed to send job completion notification: {e}")

    async def wait_for_job_result(self, job_id: str, timeout: int = 300) -> Dict[str, Any]:
        """Wait for a job to complete and return its result.

        Args:
            job_id: The ID of the job to wait for
            timeout: Maximum time to wait in seconds

        Returns:
            The job result data
        """
        start_time = time.time()
        last_status = None

        while time.time() - start_time < timeout:
            # Get job from database
            with self.get_session() as session:
                job_record = session.query(JobRecord).filter_by(id=job_id).first()
                if not job_record:
                    raise ValueError(f"Job {job_id} not found")

                # Log status changes
                if job_record.status != last_status:
                    self.logger.info(f"Job {job_id} status: {job_record.status}")
                    last_status = job_record.status

                # Check job completion status
                if job_record.status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value]:
                    self.logger.info(f"Job {job_id} completed with status: {job_record.status}")
                    return {
                        "success": job_record.success if job_record.status == JobStatus.COMPLETED.value else False,
                        "message": job_record.message,
                        "error": job_record.message if job_record.status != JobStatus.COMPLETED.value else None,
                        "data": job_record.data,
                        "outputs": job_record.outputs or [],
                    }

                # For running jobs, log progress
                if job_record.outputs:
                    self.logger.info(f"Job {job_id} has {len(job_record.outputs)} outputs while running")

                # Wait before checking again
                await asyncio.sleep(2)

        raise TimeoutError(f"Timeout waiting for job {job_id}")
