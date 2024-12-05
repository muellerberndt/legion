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
    
    async def execute(self, *args) -> str:
        """Execute the job result action"""
        job_manager = JobManager()
        
        # Parse arguments
        if not args:
            # If no arguments, list all jobs
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
        
        # First argument is job ID
        job_id = args[0]
        
        # Check for command (second argument)
        command = args[1] if len(args) > 1 else None
        
        # Handle stop command
        if command == "stop":
            success = await job_manager.stop_job(job_id)
            if success:
                return f"Successfully stopped job {job_id}"
            else:
                return f"Failed to stop job {job_id}"
        
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
        
        # Handle outputs with pagination
        MAX_OUTPUTS = 10  # Maximum number of outputs to show
        MAX_LENGTH = 500  # Maximum length per output
        
        outputs = job.result.outputs
        if outputs:
            if len(outputs) > MAX_OUTPUTS:
                lines.append(f"\nShowing first {MAX_OUTPUTS} of {len(outputs)} matches:")
                outputs = outputs[:MAX_OUTPUTS]
            
            for output in outputs:
                # Truncate long outputs
                if len(output) > MAX_LENGTH:
                    truncated = output[:MAX_LENGTH] + "..."
                    lines.append(f"\n{truncated}")
                else:
                    lines.append(f"\n{output}")
                    
            if len(outputs) > MAX_OUTPUTS:
                lines.append(f"\n... and {len(job.result.outputs) - MAX_OUTPUTS} more matches")
        else:
            lines.append("\nNo matches found")
            
        return "\n".join(lines) 