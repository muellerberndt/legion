"""Action to launch an agent with a custom prompt"""

from typing import Dict, Any
from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.jobs.manager import JobManager


class AutobotAction(BaseAction):
    """Action to launch an agent with a custom prompt"""

    spec = ActionSpec(
        name="autobot",
        description="Launch an agent with a custom prompt",
        help_text="Usage: /autobot <prompt>\nLaunches an AI agent with the specified prompt.",
        agent_hint="Use this command to start an AI agent with a custom prompt",
        arguments=[ActionArgument(name="prompt", description="The prompt to give to the agent", required=True)],
    )

    async def execute(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Execute the autobot action"""

        from src.jobs.autobot import AutobotJob

        # Create and schedule the job
        job = AutobotJob(prompt=prompt)
        job_manager = await JobManager.get_instance()
        job_id = await job_manager.submit_job(job)

        return {"success": True, "message": f"Started autobot with prompt: {prompt}", "job_id": job_id}
