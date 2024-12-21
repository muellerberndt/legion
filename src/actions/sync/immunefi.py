from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.jobs.indexer import IndexerJob
from src.jobs.manager import JobManager
from src.actions.decorators import no_autobot
from src.actions.result import ActionResult


@no_autobot
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

    async def execute(self, *args, **kwargs) -> ActionResult:
        """Execute the sync action"""
        # Check if mode is provided
        mode = args[0] if args else "normal"
        if mode == "silent":
            self.initialize_mode = True

        job = IndexerJob(platform="immunefi", initialize_mode=self.initialize_mode)
        job_manager = JobManager()
        job_id = await job_manager.submit_job(job)

        return ActionResult.job(
            job_id=job_id, metadata={"platform": "immunefi", "mode": mode, "initialize_mode": self.initialize_mode}
        )
