"""Job that runs an agent with a custom prompt"""

from datetime import datetime
from src.jobs.base import Job, JobResult
from src.ai.chatbot import Chatbot
from src.actions.result import ActionResult


class AutobotJob(Job):
    """Job that runs an agent with a custom prompt"""

    def __init__(self, prompt: str):
        super().__init__(job_type="autobot")
        self.prompt = prompt
        self.chatbot = Chatbot(max_history=10)
        self.action_results = []  # Track full results of each action

    async def start(self) -> None:
        """Start the job - required by Job base class"""
        await self.run()

    async def stop_handler(self) -> None:
        """Handle job stop request - required by Job base class"""
        pass  # Nothing special needed for cleanup

    async def run(self) -> None:
        try:
            # Process message and track results - no update_callback needed
            result = await self.chatbot.process_message(self.prompt, action_callback=self._track_action_result)

            # Create job result with action history
            job_result = JobResult(
                success=True,
                message="Autobot completed successfully",
                data={
                    "history": self.chatbot.history[1:],
                    "execution_time": (datetime.utcnow() - self.started_at).total_seconds(),
                    "action_results": self.action_results,
                    "final_result": result,
                },
            )

            # Add the result as output
            job_result.add_output(result)

            await self.complete(job_result)

        except Exception as e:
            self.logger.error(f"Autobot job failed: {str(e)}")
            await self.fail(str(e))

    async def _track_action_result(self, command: str, result: ActionResult) -> None:
        """Track the full result of an action in job data"""
        self.action_results.append(
            {"timestamp": datetime.utcnow().isoformat(), "command": command, "result": result.to_dict()}
        )
