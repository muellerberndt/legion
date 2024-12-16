from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.jobs.manager import JobManager
from src.util.logging import Logger
from src.backend.database import DBSessionMixin
from src.models.job import JobRecord


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

    async def execute(self, *args, **kwargs) -> str:
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
    """Action to get job results"""

    spec = ActionSpec(
        name="job",
        description="Get results of a job by ID",
        help_text="""Get the results or status of a background job.

Usage:
/job <job_id>

This command will show:
- Job status (running, completed, failed)
- Job results or error message
- Start and completion times
- Additional outputs if available

Example:
/job abc123  # Get results for job abc123""",
        agent_hint="Use this command to check the status and results of background jobs like scans, searches, or analysis tasks.",
        arguments=[ActionArgument(name="job_id", description="ID of the job to check", required=True)],
    )

    def __init__(self):
        DBSessionMixin.__init__(self)
        self.logger = Logger("GetJobResultAction")

    async def execute(self, job_id: str) -> str:
        """Get job results"""
        try:
            with self.get_session() as session:
                job = session.query(JobRecord).filter_by(id=job_id).first()
                if not job:
                    return f"❌ Job {job_id} not found"

                # Format job info
                lines = [f"🔍 Job {job.id}", f"Type: {job.type}", f"Status: {job.status}"]

                if job.started_at:
                    lines.append(f"Started: {job.started_at}")
                if job.completed_at:
                    lines.append(f"Completed: {job.completed_at}")

                if job.message:
                    lines.extend(["", "📝 Result:", job.message])

                if job.outputs:
                    lines.extend(["", "📄 Outputs:"])
                    for output in job.outputs:
                        # Split output into lines and indent them
                        output_lines = ["  " + line for line in output.split("\n")]
                        lines.extend(output_lines)

                return "\n".join(lines)

        except Exception as e:
            self.logger.error(f"Failed to get job results: {str(e)}")
            return f"❌ Error getting job results: {str(e)}"


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

    async def execute(self, job_id: str) -> str:
        """Stop a job"""
        try:
            job_manager = JobManager()
            await job_manager.stop_job(job_id)
            return f"Requested stop for job {job_id}"

        except Exception as e:
            self.logger.error(f"Failed to stop job: {str(e)}")
            return f"Error stopping job: {str(e)}"


# Export actions
__all__ = ["ListJobsAction", "GetJobResultAction", "StopJobAction"]
