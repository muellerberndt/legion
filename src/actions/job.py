from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.jobs.manager import JobManager
from src.util.logging import Logger
from src.actions.result import ActionResult
from src.jobs.base import JobStatus
from src.models.job import JobRecord


class ListJobsAction(BaseAction):
    """Action that lists jobs"""

    spec = ActionSpec(
        name="list_jobs",
        description="List jobs with optional status filter",
        help_text="List jobs. Use 'running' (default), 'completed', or 'all' as argument",
        arguments=[
            ActionArgument(name="status", description="Job status to filter by (running/completed/all)", required=False)
        ],
        agent_hint="Use this to check the status of jobs",
    )

    def __init__(self):
        super().__init__()
        self.logger = Logger("ListJobsAction")
        self.job_manager = JobManager()

    async def execute(self, *args, **kwargs) -> ActionResult:
        """Execute the list jobs action"""
        try:
            # Get status filter from args
            status_filter = args[0] if args else "running"

            # Validate and convert status argument
            status = None
            if status_filter.lower() == "running":
                status = JobStatus.RUNNING
            elif status_filter.lower() == "completed":
                status = JobStatus.COMPLETED  # This will include failed and cancelled
            elif status_filter.lower() == "all":
                status = None
            else:
                return ActionResult.error("Invalid status filter. Use 'running', 'completed', or 'all'")

            # Get jobs with filter
            jobs = await self.job_manager.list_jobs(status=status)

            if not jobs:
                return ActionResult.text("No jobs found")

            # Format job entries
            job_entries = []
            for job in jobs:
                # Create status indicator
                status_str = job["status"]
                if job["success"] is not None:
                    status_str += " ✓" if job["success"] else " ✗"

                # Format job entry
                entry = f"{job['id']} ({job['type']}) - {status_str}"
                # Add message if available and not too long
                if job["message"]:
                    message = job["message"]
                    if len(message) > 50:
                        message = message[:47] + "..."
                    entry += f" - {message}"

                job_entries.append(entry)

            # Return list result with metadata
            return ActionResult.list(job_entries, metadata={"title": f"📋 Jobs ({status_filter})", "count": len(jobs)})

        except Exception as e:
            self.logger.error(f"Error listing jobs: {str(e)}")
            return ActionResult.error(f"Failed to list jobs: {str(e)}")


class GetJobResultAction(BaseAction):
    """Action to get job results"""

    spec = ActionSpec(
        name="job",
        description="Get results of a job",
        help_text="""Get the results of a specific job.

Usage:
/job [job_id]

Shows:
- Job status
- Start/completion times
- Results or error messages
- Additional outputs

If no job_id is provided, shows the most recently completed job.

Examples:
/job abc123  # Get results for job abc123
/job         # Get results of most recent job""",
        agent_hint="Use this command to check the results of a previously started job",
        arguments=[ActionArgument(name="job_id", description="ID of the job to check", required=False)],
    )

    def __init__(self):
        self.logger = Logger("GetJobResultAction")

    async def execute(self, job_id: str = None) -> ActionResult:
        """Get job results"""
        try:
            job_manager = JobManager()

            # If no job ID provided, get most recent job
            if not job_id:
                job_record = job_manager.get_most_recent_finished_job()
                if not job_record:
                    return ActionResult.text("No completed jobs found.")
                job_id = job_record.id

            # First try to get running job from memory
            job = job_manager.get_job(job_id)
            if job:
                # Build job info structure for running job
                job_info = {
                    "id": job_id,
                    "type": job.type,
                    "status": job.status,
                    "started_at": job.started_at.isoformat() if job.started_at else None,
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                }

                # Add result info if available
                if job.result:
                    job_info.update(
                        {
                            "success": job.result.success,
                            "message": job.result.message,
                            "error": job.result.error,
                            "outputs": job.result.outputs,
                            "data": job.result.data,
                        }
                    )

                return ActionResult.tree(job_info)

            # If not in memory, try to get from database
            with job_manager.get_session() as session:
                job_record = session.query(JobRecord).filter_by(id=job_id).first()
                if not job_record:
                    return ActionResult.error(f"Job {job_id} not found")

                # Build job info structure from database record
                job_info = {
                    "id": job_record.id,
                    "type": job_record.type,
                    "status": job_record.status,
                    "started_at": job_record.started_at.isoformat() if job_record.started_at else None,
                    "completed_at": job_record.completed_at.isoformat() if job_record.completed_at else None,
                    "success": job_record.success,
                    "message": job_record.message,
                    "outputs": job_record.outputs,
                    "data": job_record.data,
                }

                return ActionResult.tree(job_info)

        except Exception as e:
            self.logger.error(f"Failed to get job result: {str(e)}")
            return ActionResult.error(f"Failed to get job result: {str(e)}")


class StopJobAction(BaseAction):
    """Action to stop a running job"""

    spec = ActionSpec(
        name="stop",
        description="Stop a running job",
        help_text="""Stop a currently running job.

Usage:
/stop <job_id>

This will attempt to gracefully stop the specified job.
Note that some jobs may take a moment to stop completely.

Example:
/stop abc123  # Stop job abc123""",
        agent_hint="Use this command when you need to stop a long-running job that is no longer needed or is taking too long.",
        arguments=[ActionArgument(name="job_id", description="ID of the job to stop", required=True)],
    )

    def __init__(self):
        self.logger = Logger("StopJobAction")

    async def execute(self, job_id: str) -> ActionResult:
        """Stop a job"""
        try:
            job_manager = JobManager()
            await job_manager.stop_job(job_id)
            return ActionResult.text(f"Requested stop for job {job_id}")

        except Exception as e:
            self.logger.error(f"Failed to stop job: {str(e)}")
            return ActionResult.error(f"Failed to stop job: {str(e)}")


# Export actions
__all__ = ["ListJobsAction", "GetJobResultAction", "StopJobAction"]
