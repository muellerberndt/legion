from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.jobs.manager import JobManager

class StopJobAction(BaseAction):
    """Action to stop a running job"""
    
    spec = ActionSpec(
        name="stop",
        description="Stop a running job",
        arguments=[
            ActionArgument(name="job_id", description="ID of the job to stop", required=True)
        ]
    )
    
    async def execute(self, job_id: str) -> str:
        """Execute the stop action"""
        job_manager = JobManager()
        success = await job_manager.stop_job(job_id)
        if success:
            return f"Successfully stopped job {job_id}"
        else:
            return f"Failed to stop job {job_id}"

class GetJobResultAction(BaseAction):
    """Action to get job results"""
    
    spec = ActionSpec(
        name="job",
        description="Get job results or control jobs",
        arguments=[
            ActionArgument(name="id", description="Job ID to get results for", required=False),
            ActionArgument(name="command", description="Command to execute (stop)", required=False)
        ]
    )
    
    async def execute(self, job_id: str = None, command: str = None) -> str:
        """Execute the job result action"""
        job_manager = JobManager()
        
        # Handle stop command
        if command == "stop" and job_id:
            success = await job_manager.stop_job(job_id)
            if success:
                return f"Successfully stopped job {job_id}"
            else:
                return f"Failed to stop job {job_id}"
        
        # If no job ID provided, list all jobs
        if not job_id:
            jobs = job_manager._jobs.values()
            if not jobs:
                return "No active jobs found"
                
            lines = ["Active jobs:"]
            for job in jobs:
                status = f"{job.status.value}"
                if job.result:
                    status += f" - {job.result.message}"
                lines.append(f"\nJob {job.id} ({job.type.value}):")
                lines.append(f"Status: {status}")
            return "\n".join(lines)
        
        # Get specific job results
        job = job_manager.get_job(job_id)
        
        if not job:
            return f"Job {job_id} not found"
            
        if not job.result:
            return f"Job {job_id} has no results yet"
            
        # Format the output nicely
        lines = [
            f"Job {job_id} ({job.type.value}):",
            f"Status: {job.status.value}",
            f"Success: {job.result.success}",
            f"Message: {job.result.message}",
            "\nOutputs:"
        ]
        
        for output in job.result.outputs:
            lines.append(f"- {output}")
            
        return "\n".join(lines) 