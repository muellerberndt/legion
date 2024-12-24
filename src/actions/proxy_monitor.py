"""Action to start proxy contract monitoring"""

from src.actions.base import BaseAction, ActionSpec
from src.jobs.proxy_monitor import ProxyMonitorJob
from src.jobs.manager import JobManager
from src.actions.result import ActionResult


class ProxyMonitorAction(BaseAction):
    """Action to trigger proxy contract monitoring"""

    spec = ActionSpec(
        name="proxy_monitor",
        description="Monitor proxy contracts for implementation upgrades",
        help_text="""Monitor proxy contracts for implementation upgrades.

Usage:
/proxy_monitor

This command will:
1. Check all deployed contracts in scope
2. Detect which ones are proxy contracts
3. Fetch and store their current implementations
4. Check for any recent upgrades
5. Send notifications for implementation changes

The job performs a single monitoring run and then completes.""",
        agent_hint="Use this command to check for proxy contract upgrades and fetch new implementations.",
        arguments=[],
    )

    async def execute(self, *args, **kwargs) -> ActionResult:
        """Execute the proxy monitor action"""
        try:
            # Create and submit job
            job = ProxyMonitorJob()
            job_manager = await JobManager.get_instance()
            job_id = await job_manager.submit_job(job)

            return ActionResult.job(job_id)

        except Exception as e:
            return ActionResult.error(f"Failed to start proxy monitoring: {str(e)}")
