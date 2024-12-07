"""Test implementations of agents"""

from typing import Optional
from src.agents.base_agent import BaseAgent


def create_test_agent(custom_prompt: Optional[str] = None):
    """Create a concrete implementation of BaseAgent for testing

    Args:
        custom_prompt: Optional custom prompt to add

    Returns:
        A concrete BaseAgent implementation
    """

    class _TestAgent(BaseAgent):
        """Private concrete implementation of BaseAgent"""

        async def process_message(self, message: str) -> str:
            """Test implementation of process_message"""
            return await self.chat_completion([{"role": "user", "content": message}])

    return _TestAgent(custom_prompt=custom_prompt)
