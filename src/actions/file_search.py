from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.jobs.file_search import FileSearchJob
from src.jobs.manager import JobManager
from src.util.logging import Logger
import asyncio
from typing import List

class FileSearchAction(BaseAction):
    """Action to search local files using regex and retrieve associated asset info"""
    
    spec = ActionSpec(
        name="file_search",
        description="Search local files using regex patterns and get associated asset info. Example: file_search \"function.*public\"",
        arguments=[
            ActionArgument(
                name="regex",
                description="Regular expression pattern to search for. Use quotes if pattern contains spaces.",
                required=True
            )
        ]
    )
    
    def __init__(self):
        self.logger = Logger("FileSearchAction")
        
    async def execute(self, *args: List[str]) -> str:
        """Execute the file search action"""
        try:
            # Join all arguments into a single regex pattern
            regex = " ".join(args)
            
            # Create and start the file search job
            job = FileSearchJob(regex_pattern=regex)
            job_manager = JobManager()
            await job_manager.submit_job(job)
            
            # Wait for initial results
            await asyncio.sleep(0.1)
            
            # Return job ID for tracking
            return f"File search started with job ID: {job.id}\nUse 'job {job.id}' to check results."
            
        except Exception as e:
            self.logger.error(f"Failed to start file search: {str(e)}")
            raise 