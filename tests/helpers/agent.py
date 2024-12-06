"""Helper classes for testing agents"""

import pytest
from src.agents.base_agent import BaseAgent

@pytest.mark.no_collect  # Tell pytest not to collect this class
class TestAgent(BaseAgent):
    """Concrete implementation of BaseAgent for testing"""
    
    async def process_message(self, message: str) -> str:
        """Test implementation of process_message"""
        return await self.chat_completion([
            {"role": "user", "content": message}
        ]) 