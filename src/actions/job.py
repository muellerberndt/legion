"""Job management actions"""

import tempfile
import os
from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.jobs.manager import JobManager
from src.util.logging import Logger
from src.backend.database import DBSessionMixin
from src.models.job import JobRecord
from src.services.telegram import TelegramService

class ListJobsAction(BaseAction):
    """Action to list running jobs"""
    
    spec = ActionSpec(
        name="list_jobs",
        description="List all running jobs",
        arguments=[]
    )
    
    def __init__(self):
        self.logger = Logger("ListJobsAction")
        
    async def execute(self) -> str:
        """Execute the list jobs action"""
        try:
            job_manager = JobManager()
            jobs = job_manager.list_jobs()
            
            if not jobs:
                return "No jobs found."
                
            lines = ["Running Jobs:"]
            for job in jobs:
                lines.append(f"- Job {job['id']} ({job['type']}): {job['status']}")
            return "\n".join(lines)
            
        except Exception as e:
            self.logger.error(f"Failed to list jobs: {str(e)}")
            raise

class GetJobResultAction(BaseAction, DBSessionMixin):
    """Action to get job details"""
    
    # Maximum length for text messages
    MAX_MESSAGE_LENGTH = 4096
    
    spec = ActionSpec(
        name="job",
        description="Get details of a specific job",
        arguments=[
            ActionArgument(
                name="job_id",
                description="ID of the job to get details for",
                required=True
            )
        ]
    )
    
    def __init__(self):
        DBSessionMixin.__init__(self)
        self.logger = Logger("GetJobResultAction")
        
    async def execute(self, job_id: str) -> str:
        """Execute the get job action"""
        try:
            # First try to get from active jobs
            job_manager = JobManager()
            job = job_manager.get_job(job_id)
            
            if job:
                job_dict = job.to_dict()
            else:
                # If not active, try to get from database
                with self.get_session() as session:
                    job_record = session.query(JobRecord).filter(JobRecord.id == job_id).first()
                    if not job_record:
                        return f"Job {job_id} not found."
                        
                    job_dict = {
                        'id': job_record.id,
                        'type': job_record.type,
                        'status': job_record.status,
                        'started_at': job_record.started_at,
                        'completed_at': job_record.completed_at,
                        'success': job_record.success,
                        'message': job_record.message,
                        'outputs': job_record.outputs,
                        'data': job_record.data,
                        'error': job_record.error
                    }
            
            # Format job details
            lines = [
                f"Job ID: {job_dict['id']}",
                f"Type: {job_dict['type']}",
                f"Status: {job_dict['status']}",
                f"Started: {job_dict['started_at'] or 'Not started'}",
                f"Completed: {job_dict['completed_at'] or 'Not completed'}"
            ]
            
            # Add result or error
            if job_dict.get('error'):
                lines.append(f"\nError: {job_dict['error']}")
            else:
                if job_dict.get('message'):
                    lines.append(f"\nMessage: {job_dict['message']}")
                
                # Combine outputs and data into a single result text
                result_parts = []
                
                if job_dict.get('outputs'):
                    result_parts.extend(job_dict['outputs'])
                    
                if job_dict.get('data'):
                    result_parts.append("\nData:")
                    result_parts.append(str(job_dict['data']))
                
                if result_parts:
                    result_text = "\n".join(result_parts)
                    
                    # If result is too long, send as file
                    if len(result_text) > self.MAX_MESSAGE_LENGTH:
                        # Create temporary file
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                            f.write(result_text)
                            temp_path = f.name
                        
                        try:
                            # Send file via Telegram
                            telegram = TelegramService.get_instance()
                            await telegram.send_file(
                                file_path=temp_path,
                                caption=f"Job output for {job_dict['id']}"
                            )
                            
                            # Add note about file being sent
                            lines.append("\nOutput has been sent as a file due to length.")
                            
                        finally:
                            # Clean up temp file
                            os.unlink(temp_path)
                    else:
                        # Add output directly to message
                        lines.append("\nResults:")
                        lines.append(result_text)
                else:
                    lines.append("\nNo results available.")
                
            return "\n".join(lines)
            
        except Exception as e:
            self.logger.error(f"Failed to get job details: {str(e)}")
            raise

class StopJobAction(BaseAction):
    """Action to stop a running job"""
    
    spec = ActionSpec(
        name="stop",
        description="Stop a running job",
        arguments=[
            ActionArgument(
                name="job_id",
                description="ID of the job to stop",
                required=True
            )
        ]
    )
    
    def __init__(self):
        self.logger = Logger("StopJobAction")
        
    async def execute(self, job_id: str) -> str:
        """Execute the stop job action"""
        try:
            job_manager = JobManager()
            job = job_manager.get_job(job_id)
            
            if not job:
                return f"Job {job_id} not found."
                
            job.cancel()
            return f"Job {job_id} has been stopped."
            
        except Exception as e:
            self.logger.error(f"Failed to stop job: {str(e)}")
            raise

# Export actions
__all__ = ['ListJobsAction', 'GetJobResultAction', 'StopJobAction'] 