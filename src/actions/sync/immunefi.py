from src.actions.base import BaseAction, ActionSpec
from src.jobs.indexer import IndexerJob


class ImmunefiSyncAction(BaseAction):
    """Action to sync data from Immunefi"""

    spec = ActionSpec(
        name="immunefi",
        description="Sync data from Immunefi",
        help_text="""Synchronize bounty program data from Immunefi.

Usage:
/sync immunefi

This command will:
1. Fetch latest bounty program data
2. Update project information
3. Download and index smart contracts
4. Track changes in scope and rewards

Example:
/sync immunefi  # Sync all Immunefi data""",
        agent_hint="Use this command to update the local database with the latest information from Immunefi bounty programs.",
        arguments=[],
    )

    def __init__(self, initialize_mode: bool = False):
        """Initialize the action"""
        self.initialize_mode = initialize_mode

    async def execute(self, *args, **kwargs) -> str:
        """Execute the sync action"""
        # Import JobManager here to avoid circular imports
        from src.jobs.manager import JobManager

        job = IndexerJob(platform="immunefi", initialize_mode=self.initialize_mode)
        job_manager = JobManager()
        job_id = await job_manager.submit_job(job)
        return f"Started Immunefi sync (Job ID: {job_id})"
