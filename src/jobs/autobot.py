"""Job that runs an agent with a custom prompt"""

from typing import Dict, Any
from datetime import datetime
from src.jobs.base import Job, JobResult
from src.agents.base_agent import BaseAgent


class AutobotJob(Job):
    """Job that runs an agent with a custom prompt"""
    
    def __init__(self, prompt: str):
        super().__init__(job_type="autobot")
        self.prompt = prompt
        self.agent = BaseAgent()
        
    async def start(self) -> None:
        """Start the autobot job"""
        try:
            self.started_at = datetime.utcnow()
            
            # Create task for the agent
            task = {
                "prompt": self.prompt,
                "timestamp": self.started_at.isoformat()
            }
            
            # Execute the task
            result = await self.agent.execute_task(task)
            
            # Create job result
            job_result = JobResult(
                success=True,
                message=f"Autobot completed task",
                data={
                    "prompt": self.prompt,
                    "response": result.get("response"),
                    "execution_time": (datetime.utcnow() - self.started_at).total_seconds()
                }
            )
            
            # Add agent's response to outputs
            job_result.add_output(result.get("response", "No response"))
            
            self.complete(job_result)
            
        except Exception as e:
            self.fail(str(e))
            
    async def stop_handler(self) -> None:
        """Handle cleanup when stopping the job"""
        # No special cleanup needed for autobot jobs
        pass 