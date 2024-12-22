"""Job that runs an agent with a custom prompt"""

from datetime import datetime
from src.jobs.base import Job, JobResult
from src.ai.chatbot import Chatbot


class AutobotJob(Job):
    """Job that runs an agent with a custom prompt"""

    def __init__(self, prompt: str):
        super().__init__(job_type="autobot")
        self.prompt = prompt
        self.chatbot = Chatbot(max_history=10)  # Keep some history in case it's needed

    async def start(self) -> None:
        """Start the job - required by Job base class"""
        await self.run()

    async def run(self) -> None:
        try:
            # Use regular chatbot functionality
            result = await self.chatbot.process_message(self.prompt)

            # Create job result
            job_result = JobResult(
                success=True,
                message="Autobot completed successfully",
                data={
                    "history": self.chatbot.history[1:],  # Keep history in data for reference
                    "execution_time": (datetime.utcnow() - self.started_at).total_seconds(),
                },
            )

            # Add the result as an output
            job_result.add_output(result)

            await self.complete(job_result)

        except Exception as e:
            self.logger.error(f"Autobot job failed: {str(e)}")
            await self.fail(str(e))

    async def stop_handler(self) -> None:
        """Handle cleanup when stopping the job"""
        # No special cleanup needed for autobot jobs
