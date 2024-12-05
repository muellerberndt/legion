from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.util.logging import Logger
from openai import AsyncOpenAI
from src.config.config import Config

class AgentAction(BaseAction):
    """Action to spawn a new AI agent"""
    
    spec = ActionSpec(
        name="agent",
        description="Spawn a new AI agent with given instructions",
        arguments=[
            ActionArgument(name="prompt", description="Instructions for the agent", required=True)
        ]
    )
    
    def __init__(self):
        self.logger = Logger("AgentAction")
        self.config = Config()
        self.client = AsyncOpenAI(api_key=self.config.openai_api_key)
    
    async def execute(self, prompt: str) -> str:
        """Execute the agent action"""
        # Clean up the prompt - remove quotes and extra whitespace
        prompt = prompt.strip().strip('"\'')
        if not prompt:
            return "Please provide a non-empty prompt"
            
        try:
            # Process the prompt directly
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
            return f"Error: {str(e)}" 