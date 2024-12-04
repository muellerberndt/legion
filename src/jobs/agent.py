import asyncio
from typing import Optional, List, Dict, Any
from src.jobs.base import Job, JobType, JobResult, JobStatus
from src.config.config import Config
from src.util.logging import Logger
from openai import AsyncOpenAI
from src.interfaces.base import Message
from src.actions.result import ActionResult
import json
from datetime import datetime
import uuid

class AgentJob(Job):
    """Job that runs an AI agent"""
    
    def __init__(self, prompt: str):
        super().__init__(JobType.AGENT)
        self.prompt = prompt
        self.logger = Logger("AgentJob")
        self.config = Config()
        self.client = AsyncOpenAI(api_key=self.config.openai_api_key)
        self.session_id = str(uuid.uuid4())
        self.result = JobResult(success=True, message="", data={})
        
    async def start(self) -> None:
        """Start the agent job"""
        try:
            # Import here to avoid circular imports
            from src.actions.registry import ActionRegistry
            
            self.action_registry = ActionRegistry()
            self.started_at = datetime.utcnow()
            self.status = JobStatus.RUNNING
            
            # Process the prompt
            response = await self._process_prompt(self.prompt)
            
            if response:
                self.result.message = response
                self.result.add_output(response)
                
            self.completed_at = datetime.utcnow()
            self.status = JobStatus.COMPLETED
            
        except Exception as e:
            self.logger.error(f"Agent job failed: {str(e)}")
            self.status = JobStatus.FAILED
            self.error = str(e)
            raise
            
    async def stop(self) -> None:
        """Stop the agent job"""
        self.status = JobStatus.CANCELLED
        
    async def _process_prompt(self, prompt: str) -> str:
        """Process a prompt and return response"""
        try:
            response = await self.client.chat.completions.create(
                model=self.config.openai_model,
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            return response.choices[0].message.content
            
        except Exception as e:
            self.logger.error(f"Failed to process prompt: {str(e)}")
            raise
        