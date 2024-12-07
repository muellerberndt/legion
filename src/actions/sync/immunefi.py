from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.jobs.indexer import IndexerJob


class ImmunefiSyncAction(BaseAction):
    """Action to sync data from Immunefi"""

    spec = ActionSpec(
        name="immunefi",
        description="Sync data from Immunefi",
        help_text="""Synchronize bounty program data from Immunefi.

Usage:
/immunefi [mode]

This command will:
1. Fetch latest bounty program data
2. Update project information
3. Download and index smart contracts
4. Track changes in scope and rewards

Arguments:
mode  Sync mode: 'normal' (default) or 'silent' (no notifications)

Examples:
/immunefi         # Regular sync with notifications
/immunefi silent  # Silent sync for initialization""",
        agent_hint="Use this command to update the local database with the latest information from Immunefi bounty programs.",
        arguments=[
            ActionArgument(
                name="mode",
                description="Sync mode: 'normal' or 'silent'",
                required=False,
            ),
        ],
    )

    def __init__(self, initialize_mode: bool = False):
        """Initialize the action"""
        self.initialize_mode = initialize_mode

    async def execute(self, *args, **kwargs) -> str:
        """Execute the sync action"""
        # Import JobManager here to avoid circular imports
        from src.jobs.manager import JobManager

        # Check if mode is provided
        mode = args[0] if args else "normal"
        if mode == "silent":
            self.initialize_mode = True

        job = IndexerJob(platform="immunefi", initialize_mode=self.initialize_mode)
        job_manager = JobManager()
        job_id = await job_manager.submit_job(job)

        if mode == "silent":
            return f"Started silent Immunefi sync (Job ID: {job_id})"
        return f"Started Immunefi sync (Job ID: {job_id})"
