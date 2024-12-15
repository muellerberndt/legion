"""Job that runs an agent with a custom prompt"""

from datetime import datetime
from src.jobs.base import Job, JobResult
from src.ai.autobot import Autobot
from src.actions.registry import ActionRegistry


class AutobotJob(Job):
    """Job that runs an agent with a custom prompt"""

    def __init__(self, prompt: str):
        super().__init__(job_type="autobot")
        self.prompt = prompt
        # Get the singleton instance of ActionRegistry that's already initialized
        action_registry = ActionRegistry()
        action_registry.initialize()
        self.agent = Autobot(action_registry=action_registry)

    async def start(self) -> None:
        """Start the autobot job"""
        try:
            self.started_at = datetime.utcnow()

            # Create task for the agent
            task = {"prompt": self.prompt, "timestamp": self.started_at.isoformat()}

            # Execute the task
            result = await self.agent.execute_task(task)

            # Create job result
            job_result = JobResult(
                success=result.success,
                message=(
                    str(result.data.get("result")) if result.data and "result" in result.data else "Autobot completed task"
                ),
                data={
                    "prompt": self.prompt,
                    "response": result.data.get("result") if result.data else None,
                    "execution_time": (datetime.utcnow() - self.started_at).total_seconds(),
                },
            )

            # Add agent's response to outputs
            if result.data and "result" in result.data:
                result_data = result.data["result"]
                if isinstance(result_data, dict) and "execution_summary" in result_data:
                    # Handle enhanced result format with summary
                    job_result.add_output(str(result_data["final_result"]))
                    job_result.add_output("\n\nExecution Summary:")
                    job_result.add_output(str(result_data["execution_summary"]))
                    if "note" in result_data:
                        job_result.add_output(f"\nNote: {result_data['note']}")
                else:
                    # Handle simple result format
                    job_result.add_output(str(result_data))
            elif result.error:
                job_result.add_output(f"Error: {result.error}")

            await self.complete(job_result)

        except Exception as e:
            await self.fail(str(e))

    async def stop_handler(self) -> None:
        """Handle cleanup when stopping the job"""
        # No special cleanup needed for autobot jobs
        pass
