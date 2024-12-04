from typing import Dict, List, Type
from src.jobs.base import Job, JobStatus
from src.util.logging import Logger
import asyncio

class JobManager:
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
            self.logger.info(f"Stopping job {job_id}")
            await job.stop()
            job.status = JobStatus.CANCELLED
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop job {job_id}: {e}")
            return False
        
    def register_job(self, job: Job) -> None:
        """Register a job with the manager"""
        if job.id in self._jobs:
            self.logger.warning(f"Job {job.id} already registered")
            return
            
        self._jobs[job.id] = job
        self.logger.info(f"Registered job: {job.id}")
        
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
            # Register the job first
            self.register_job(job)
            
            # Start the job
            await job.start()
            
            return job.id
            
        except Exception as e:
            self.logger.error(f"Failed to submit job: {str(e)}")
            # Clean up registration if start failed
            if job.id in self._jobs:
                del self._jobs[job.id]
            raise