from typing import Dict, List, Any, Optional
from src.agents.base_agent import BaseAgent, AgentCommand
from src.util.logging import Logger

class ConversationAgent(BaseAgent):
    """Agent for handling natural language conversations with users
    
    This agent:
    1. Processes natural language queries
    2. Executes appropriate commands based on user intent
    3. Provides helpful responses and suggestions
    4. Maintains conversation context
    """
    
    def __init__(self, command_names: Optional[List[str]] = None):
        self.logger = Logger("ConversationAgent")
        
        # Add specialized prompt for conversation handling
        custom_prompt = """You are specialized in having helpful conversations with security researchers.

Your responsibilities:
1. Understand user queries and intent
2. Execute appropriate commands to fulfill requests
3. Provide clear, concise responses
4. Guide users toward security-relevant information
5. Maintain context across conversation turns

Communication style:
- Be professional but conversational
- Focus on security relevance
- Provide specific, actionable information
- Ask clarifying questions when needed
- Use clear formatting for better readability"""

        # Call parent constructor with custom prompt and command names
        super().__init__(custom_prompt=custom_prompt, command_names=command_names)
        
    async def process_message(self, message: str) -> str:
        """Process a user message and return a response
        
        Args:
            message: User's message
            
        Returns:
            Response text
        """
        try:
            # Get AI response
            messages = [{"role": "user", "content": message}]
            response = await self.chat_completion(messages)
            
            # Extract and execute any commands from the response
            # TODO: Implement command extraction and execution
            
            return response
            
        except Exception as e:
            self.logger.error(f"Failed to process message: {str(e)}")
            return f"I encountered an error: {str(e)}" 