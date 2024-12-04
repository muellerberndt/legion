from typing import List, Dict, Any
from src.util.logging import Logger
from openai import AsyncOpenAI
from src.config.config import Config
import json

class ConversationAgent:
    """Agent that maintains conversation context and can execute actions"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.logger = Logger(f"ConversationAgent-{session_id}")
        self.config = Config()
        
        # Get OpenAI configuration
        try:
            openai_key = self.config.openai_api_key
            self.client = AsyncOpenAI(api_key=openai_key)
            self.model = self.config.openai_model
            self.logger.info(f"Using OpenAI model: {self.model}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenAI: {e}")
            raise
        
        self.messages: List[Dict[str, str]] = []
        self.action_registry = None  # Lazy load to avoid circular imports
        
    def _get_system_prompt(self) -> str:
        """Get the system prompt including available actions"""
        from src.actions.registry import ActionRegistry
        if not self.action_registry:
            self.action_registry = ActionRegistry()
            
        actions = self._get_available_actions()
        return (
            "You are r4dar bot, an AI assistant designed to help Web3 security researchers and bug hunters find high-value "
            "vulnerabilities in smart contracts. Your mission is to help researchers efficiently analyze and discover security "
            "issues in bug bounty programs and audit contests.\n\n"
            "IMPORTANT: You MUST respond with JSON. Every response MUST be a valid JSON object.\n\n"
            f"Available actions:\n{actions}\n\n"
            "For any questions about finding or searching through projects, assets, or files, use the natural language search command:\n"
            '{"action": "search", "args": ["your natural language query here"]}\n\n'
            "Example search queries:\n"
            '1. {"action": "search", "args": ["Find all projects with high-value bounties"]}\n'
            '2. {"action": "search", "args": ["Show me Cairo smart contracts"]}\n'
            '3. {"action": "search", "args": ["List GitHub repositories with reentrancy vulnerabilities"]}\n'
            '4. {"action": "search", "args": ["Find deployed contracts that use delegatecall"]}\n\n'
            "For normal conversation, respond with JSON:\n"
            '{"response": "your message here"}\n\n'
            "Remember:\n"
            "- You MUST ALWAYS respond in valid JSON format\n"
            "- Every single response must be a JSON object\n"
            "- You are a security research assistant focused on finding vulnerabilities\n"
            "- Always think about potential security implications\n"
            "- Suggest relevant vulnerability patterns to look for\n"
            "- Help prioritize high-value targets\n"
            "- Keep track of context and suggest relevant follow-up searches\n"
            "- For ANY query about finding, searching, or listing data, use the search command\n"
            "- The search command understands natural language, so pass the user's query directly\n"
            "\nIMPORTANT: Remember that EVERY response MUST be a valid JSON object."
        )
        
    def _get_available_actions(self) -> str:
        """Get formatted list of available actions with their specs"""
        lines = []
        for name, (handler, spec) in self.action_registry.actions.items():
            if spec:
                # Add action name and description
                lines.append(f"\n{name}:")
                lines.append(f"  Description: {spec.description}")
                
                # Add arguments if any
                if spec.arguments:
                    lines.append("  Arguments:")
                    for arg in spec.arguments:
                        required = "(required)" if arg.required else "(optional)"
                        lines.append(f"    - {arg.name}: {arg.description} {required}")
                        
                # Add example if available
                if hasattr(spec, 'example') and spec.example:
                    lines.append(f"  Example: {spec.example}")
                    
        return "\n".join(lines)
        
    async def process_message(self, content: str) -> str:
        """Process a message and return response"""
        # Add user message to history with explicit JSON requirement
        self.messages.append({
            "role": "user",
            "content": f"{content}\n\nRespond with a JSON object that either contains an action to execute or a direct response."
        })
        
        try:
            # Get response from GPT
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    *self.messages
                ],
                temperature=0.7,
                response_format={"type": "json_object"}  # Force JSON response
            )
            
            # Parse and handle response
            agent_message = response.choices[0].message.content
            self.logger.info(f"Raw GPT response: {agent_message}")
            
            # Clean up markdown formatting if present
            if agent_message.startswith('```'):
                agent_message = agent_message.split('\n', 1)[1]  # Remove first line with ```json
            if agent_message.endswith('```'):
                agent_message = agent_message.rsplit('\n', 1)[0]  # Remove last line with ```
                
            self.logger.info(f"Cleaned response: {agent_message}")
            self.messages.append({"role": "assistant", "content": agent_message})
            
            try:
                data = json.loads(agent_message)
                self.logger.info(f"Parsed JSON: {data}")
                
                # Handle action execution
                if 'action' in data:
                    self.logger.info(f"Executing action: {data['action']} with args: {data.get('args', {})}")
                    action_result = await self._execute_action(
                        data['action'],
                        data.get('args', {})
                    )
                    self.logger.info(f"Action result: {action_result}")
                    
                    # Add result to conversation history
                    self.messages.append({
                        "role": "system",
                        "content": f"Action result (respond with JSON): {action_result}"
                    })
                    
                    # Get next response from GPT to analyze the result
                    analysis = await self.client.chat.completions.create(
                        model=self.model,
                        messages=self.messages,  # Use full conversation history
                        temperature=0.7,
                        response_format={"type": "json_object"}  # Force JSON response
                    )
                    
                    analysis_text = analysis.choices[0].message.content
                    self.logger.info(f"Analysis response: {analysis_text}")
                    
                    try:
                        formatted_data = json.loads(analysis_text)
                        if 'response' in formatted_data:
                            return str(formatted_data['response'])
                        return action_result
                    except json.JSONDecodeError as e:
                        self.logger.error(f"Failed to parse analysis JSON: {e}")
                        return action_result
                    
                # Handle normal response
                elif 'response' in data:
                    return str(data['response'])
                else:
                    return "I'm not sure how to respond to that."
                    
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse GPT response as JSON: {e}")
                return "I encountered an error processing that request."
            
        except Exception as e:
            self.logger.error(f"Error in conversation: {e}")
            return f"Sorry, I encountered an error: {str(e)}"
            
    async def _execute_action(self, action: str, args: List[str]) -> str:
        """Execute an action with the given arguments"""
        try:
            if not self.action_registry:
                self.action_registry = ActionRegistry()
                
            # Get the action handler
            action_tuple = self.action_registry.get_action(action)
            if not action_tuple:
                return f"Unknown action: {action}"
                
            handler, spec = action_tuple
            
            # Create message object
            from src.interfaces.base import Message
            message = Message(
                session_id=self.session_id,
                content=action,
                arguments=args
            )
            
            # Special handling for search action to pass query parameter
            if action == "search":
                query = " ".join(args)  # Join all args into a single query string
                return await handler(message, query)
                
            # Default handling for other actions
            return await handler(message, *args)
            
        except Exception as e:
            self.logger.error(f"Action failed: {str(e)}")
            return str(e) 