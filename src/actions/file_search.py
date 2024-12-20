from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.jobs.file_search import FileSearchJob
from src.jobs.manager import JobManager
from src.util.logging import Logger
from src.actions.result import ActionResult


class FileSearchAction(BaseAction):
    """Action to search files using regex"""

    spec = ActionSpec(
        name="file_search",
        description="Search files using regex pattern with optional project filter",
        help_text="""Search through files using a regular expression pattern.

Usage:
/file_search <pattern> [project-ids]

Arguments:
- pattern: Regular expression pattern to search for
- project-ids: Optional comma-separated list of project IDs to filter by (e.g. "1,2,3")

The search will:
1. Look through files in the database (filtered by project if specified)
2. Match the regex pattern against file contents
3. Return matches with context

Examples:
/file_search 'function\\s+transfer'           # Search all projects
/file_search 'function\\s+transfer' 1,2,3     # Search only in projects 1, 2, and 3""",
        agent_hint="Use this command to search through files using regex patterns, optionally filtered by project IDs",
        arguments=[
            ActionArgument(name="pattern", description="Regex pattern to search for", required=True),
            ActionArgument(name="project_ids", description="Optional comma-separated list of project IDs", required=False),
        ],
    )

    def __init__(self):
        self.logger = Logger("FileSearchAction")

    async def execute(self, *args, **kwargs) -> ActionResult:
        """Execute the file search action"""
        try:
            if not args:
                return ActionResult.error("Please provide a search pattern")

            # First argument is the regex pattern
            regex = args[0]

            # Parse project IDs if provided
            project_ids = None
            if len(args) > 1:
                try:
                    project_ids = [int(pid.strip()) for pid in args[1].split(",")]
                except ValueError:
                    return ActionResult.error("Invalid project IDs format. Use comma-separated integers (e.g. '1,2,3')")

            # Create and submit the file search job
            job = FileSearchJob(regex_pattern=regex, project_ids=project_ids)
            job_manager = JobManager()
            job_id = await job_manager.submit_job(job)

            # Return job ID for tracking
            msg = f"File search started with job ID: {job_id}"
            if project_ids:
                msg += f"\nSearching in projects: {', '.join(str(pid) for pid in project_ids)}"
            msg += f"\nUse 'job {job_id}' to check results."

            return ActionResult.text(msg)

        except Exception as e:
            self.logger.error(f"Failed to start file search: {str(e)}")
            return ActionResult.error(f"Failed to start file search: {str(e)}")
