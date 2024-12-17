from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.jobs.manager import JobManager
from src.util.logging import Logger
from src.actions.result import ActionResult


class ListJobsAction(BaseAction):
    """Action to list running jobs"""

    spec = ActionSpec(
        name="list_jobs",
        description="List all running jobs",
        help_text="""List all currently running jobs in the system.

Usage:
/list_jobs

Shows information about:
- Job IDs
- Job types
- Current status
- Start times (if available)

Example:
/list_jobs  # Show all running jobs""",
        agent_hint="Use this command to see what jobs are currently running in the system and monitor their status.",
        arguments=[],
    )

    def __init__(self):
        BaseAction.__init__(self)
        self.logger = Logger("ListJobsAction")

    async def execute(self, *args, **kwargs) -> ActionResult:
        """Execute the list jobs action"""
        try:
            job_manager = JobManager()
            jobs = job_manager.list_jobs()

            if not jobs:
                return ActionResult.text("No jobs found.")

            # Format as table
            headers = ["ID", "Type", "Status", "Started", "Completed"]
            rows = []
            for job in jobs:
                rows.append(
                    [
                        job["id"],
                        job["type"],
                        job["status"],
                        job["started_at"] or "Not started",
                        job["completed_at"] or "Not completed",
                    ]
                )

            return ActionResult.table(headers=headers, rows=rows)

        except Exception as e:
            self.logger.error(f"Failed to list jobs: {str(e)}")
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

            # Get the job
            job = job_manager.get_job(job_id)
            if not job:
                return ActionResult.error(f"Job {job_id} not found")

            # Build job info structure
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
