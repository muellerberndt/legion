from typing import Dict, List, Type
from src.jobs.base import Job, JobStatus
from src.util.logging import Logger
import asyncio
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
        self._running = False
        
    async def start(self) -> None:
        """Start the job manager and all registered jobs"""
        if self._running:
            return
            
        self.logger.info("Starting job manager")
        self._running = True
        
        # Start all registered jobs
        for name, job in self._jobs.items():
            try:
                self.logger.info(f"Starting job: {name}")
                await job.start()
            except Exception as e:
                self.logger.error(f"Failed to start job {name}: {e}")
                
    async def stop(self) -> None:
        """Stop all running jobs"""
        if not self._running:
            return
            
        self.logger.info("Stopping job manager")
        
        # Stop all jobs
        stop_tasks = []
        for name, job in self._jobs.items():
            try:
                self.logger.info(f"Stopping job: {name}")
                stop_tasks.append(job.stop())
            except Exception as e:
                self.logger.error(f"Failed to stop job {name}: {e}")
                
        if stop_tasks:
            await asyncio.gather(*stop_tasks)
            
        self._running = False
        self._jobs.clear()
        
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
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop job {job_id}: {e}")
            return False
        
    def register_job(self, job: Job) -> JobRecord:
        """Register a job with the manager and create database record
        
        Args:
            job: The job to register
            
        Returns:
            The created job record
        """
        if job.id in self._jobs:
            self.logger.warning(f"Job {job.id} already registered")
            return None
            
        self._jobs[job.id] = job
        self.logger.info(f"Registered job: {job.id}")
        
        # Create job record in database
        with self.get_session() as session:
            job_record = JobRecord(
                id=job.id,
                type=job.type.value,
                status=job.status.value,
                created_at=datetime.utcnow()
            )
            session.add(job_record)
            return job_record
        
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
        try:
            # Import here to avoid circular imports
            from src.jobs.notification import JobNotifier
            
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
                else:
                    self._jobs[job.id] = job
                    self.logger.info(f"Registered job: {job.id}")
                
                # Start the job
                await job.start()
                
                # Update record with completion status
                job_record.status = job.status.value
                job_record.completed_at = datetime.utcnow() if job.status == JobStatus.COMPLETED else None
                job_record.error = job.error
                if job.result:
                    job_record.success = job.result.success
                    job_record.message = job.result.message
                    job_record.data = job.result.data
                    job_record.outputs = job.result.outputs  # Save outputs to database
                
                # Commit all changes in one transaction
                session.commit()
                
                # Send completion notification
                notifier = JobNotifier()
                await notifier.notify_completion(
                    job_id=job.id,
                    job_type=job.type.value,
                    status=job.status.value,
                    message=job.result.message if job.result else job.error or "No result",
                    started_at=job.started_at,
                    completed_at=job.completed_at
                )
            
            return job.id
            
        except Exception as e:
            self.logger.error(f"Failed to submit job: {str(e)}")
            # Clean up registration if start failed
            if job.id in self._jobs:
                del self._jobs[job.id]
            raise
        
    async def update_job_status(self, job_id: str, status: JobStatus) -> None:
        """Update job status and send notification
        
        Args:
            job_id: ID of the job to update
            status: New job status
        """
        job = self._jobs.get(job_id)
        if not job:
            self.logger.warning(f"Job {job_id} not found")
            return
            
        try:
            # Import here to avoid circular imports
            from src.jobs.notification import JobNotifier
            
            # Update job status
            job.status = status
            if status == JobStatus.COMPLETED:
                job.completed_at = datetime.utcnow()
            
            # Update database record
            with self.get_session() as session:
                job_record = session.query(JobRecord).filter(JobRecord.id == job_id).first()
                if job_record:
                    job_record.status = status.value
                    job_record.completed_at = job.completed_at
                    job_record.error = job.error
                    if job.result:
                        job_record.success = job.result.success
                        job_record.message = job.result.message
                        job_record.data = job.result.data
                        job_record.outputs = job.result.outputs
                    session.commit()
            
            # Send notification
            notifier = JobNotifier()
            await notifier.notify_completion(
                job_id=job.id,
                job_type=job.type.value,
                status=status.value,
                message=job.result.message if job.result else job.error or "No result",
                started_at=job.started_at,
                completed_at=job.completed_at
            )
            
        except Exception as e:
            self.logger.error(f"Failed to update job status: {str(e)}")
            raise