"""Action to generate embeddings for assets"""

from src.actions.base import BaseAction, ActionSpec
from src.jobs.embed import EmbedJob
from src.jobs.manager import JobManager
from src.util.logging import Logger
from src.actions.result import ActionResult


class EmbeddingsAction(BaseAction):
    """Action to generate embeddings for all assets"""

    spec = ActionSpec(
        name="embeddings",
        description="Generate embeddings for all assets in the database",
        help_text="""Generate vector embeddings for semantic search

Usage:
/embeddings

This command starts a job that:
1. Iterates through all assets in the database
2. For each asset:
   - For single files: generates embedding from file content
   - For directories (contracts/repos): combines embeddings of all files
3. Stores the embeddings in the database for semantic search

The embeddings are generated using OpenAI's text-embedding model.
Returns a job ID that can be used to track progress.

Example:
/embeddings
""",
        agent_hint="Use this command to generate embeddings for all assets in the database to enable semantic search",
        arguments=[],
    )

    def __init__(self):
        self.logger = Logger("EmbeddingsAction")

    async def execute(self, *args, **kwargs) -> ActionResult:
        """Start the embedding generation job"""
        try:
            # Create and submit the job
            job = EmbedJob()
            job_manager = JobManager()
            job_id = await job_manager.submit_job(job)

            return ActionResult.job(job_id)

        except Exception as e:
            self.logger.error(f"Failed to start embedding job: {str(e)}")
            return ActionResult.error(f"Failed to start embedding job: {str(e)}")
