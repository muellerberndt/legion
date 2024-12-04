from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.jobs.manager import JobManager
import asyncio

class AgentAction(BaseAction):
    """Action to spawn a new AI agent"""
    
    spec = ActionSpec(
        name="agent",
        description="Spawn a new AI agent with given instructions",
        arguments=[
            ActionArgument(name="prompt", description="Instructions for the agent", required=True)
        ]
    )
    
    async def execute(self, prompt: str) -> str:
        """Execute the agent action"""
        # Import here to avoid circular imports
        from src.jobs.agent import AgentJob
        
        # Clean up the prompt - remove quotes and extra whitespace
        prompt = prompt.strip().strip('"\'')
        if not prompt:
            return "Please provide a non-empty prompt"
            
        # Create and submit job through job manager
        job = AgentJob(prompt=prompt)
        job_manager = JobManager()
        job_id = await job_manager.submit_job(job)
        
        # Wait for initial response
        while not job.result or not job.result.message:
            await asyncio.sleep(0.1)
            
        return f"Started agent with job ID: {job_id}\nInitial response: {job.result.message}" 