from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.jobs.file_search import FileSearchJob
from src.jobs.manager import JobManager
from src.util.logging import Logger
from src.actions.result import ActionResult


class FileSearchAction(BaseAction):
    """Action to search files using regex"""

    spec = ActionSpec(
        name="file_search",
        description="Search files using regex pattern",
        help_text="""Search through files using a regular expression pattern.

Usage:
/file_search <pattern>

The search will:
1. Look through all files in the database
2. Match the regex pattern against file contents
3. Return matches with context

Example:
/file_search 'function\\s+transfer'""",
        agent_hint="Use this command to search through files using regex patterns",
        arguments=[ActionArgument(name="pattern", description="Regex pattern to search for", required=True)],
    )

    def __init__(self):
        self.logger = Logger("FileSearchAction")

    async def execute(self, *args, **kwargs) -> ActionResult:
        """Execute the file search action"""
        try:
            # Join all arguments into a single regex pattern
            regex = " ".join(args)

            # Create and submit the file search job
            job = FileSearchJob(regex_pattern=regex)
            job_manager = JobManager()
            job_id = await job_manager.submit_job(job)

            # Return job ID for tracking
            return ActionResult.text(f"File search started with job ID: {job_id}\nUse 'job {job_id}' to check results.")

        except Exception as e:
            self.logger.error(f"Failed to start file search: {str(e)}")
            return ActionResult.error(f"Failed to start file search: {str(e)}")
