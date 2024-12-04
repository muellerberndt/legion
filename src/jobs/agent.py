import asyncio
from typing import Optional, List, Dict, Any
from src.jobs.base import Job, JobType, JobResult
from src.config.config import Config
from src.util.logging import Logger
from openai import AsyncOpenAI
from src.interfaces.base import Message
from src.actions.result import ActionResult
import json
from datetime import datetime
from src.actions.registry import ActionRegistry
import uuid

class AgentJob(Job):
    """Job that runs an autonomous AI agent"""
    
    def __init__(self, prompt: str):
        super().__init__(JobType.AGENT)
        self.prompt = prompt
        self.logger = Logger("AgentJob")
        self.config = Config()
        self.action_registry = ActionRegistry()
        self.client = AsyncOpenAI(
            api_key=self.config.openai_api_key
        )
        self.model = self.config.openai_model
        self.session_id = str(uuid.uuid4())
        
    def get_system_prompt(self) -> str:
        """Get the system prompt including available actions"""
        actions = self._get_available_actions()
        return (
            "You are an AI assistant that helps with various tasks. "
            "Your goal is to accomplish the user's request and provide a clear final result.\n\n"
            "For simple requests like repeating text or basic responses, "
            "use return action immediately with the response.\n\n"
            f"For complex tasks, you have access to these actions:\n{actions}\n\n"
            "You MUST respond with JSON. Your response MUST be a valid JSON object with this format:\n"
            "{'action': 'action_name', 'args': {'arg1': 'value1', 'arg2': 'value2'}}\n\n"
            "Example flows:\n"
            "1. Simple request: 'Repeat: Hello world'\n"
            "   {'action': 'return', 'args': {'result': 'Hello world'}}\n\n"
            "2. Complex task: 'How many projects are there?'\n"
            "   {'action': 'list', 'args': {'type': 'projects'}}\n"
            "   ... analyze results ...\n"
            "   {'action': 'return', 'args': {'result': 'Found 5 projects in total'}}\n\n"
            "3. Search request: 'Find GitHub repositories'\n"
            "   {'action': 'db_search', 'args': {'query': 'search assets type=github_repo'}}\n\n"
            "Always return a clear and concise final result that directly answers the user's request.\n"
            "Remember: Your response MUST be a valid JSON object."
        )
        
    def _get_available_actions(self) -> str:
        """Get formatted list of available actions with their specs"""
        lines = []
        for action_name, (handler, spec) in self.action_registry.actions.items():
            if spec:
                args = []
                if spec.arguments:
                    args = [f"{arg.name}: {arg.description}" for arg in spec.arguments]
                args_str = "\n  - " + "\n  - ".join(args) if args else ""
                lines.extend([
                    f"\n{action_name}:",
                    f"  Description: {spec.description}",
                    f"  Arguments: {args_str}"
                ])
            else:
                lines.append(f"\n{action_name}: No arguments required")
        return "\n".join(lines)
        
    async def start(self) -> None:
        """Start the agent"""
        try:
            self.logger.info(f"Starting agent with prompt: '{self.prompt}'")
            self.result = JobResult(success=True, message="Agent started")
            messages = [
                {"role": "system", "content": self.get_system_prompt()},
                {"role": "user", "content": self.prompt}
            ]
            
            while True:
                # Log the messages being sent to GPT
                self.logger.info(f"Sending messages to GPT: {messages}")
                
                # Get response from GPT
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    response_format={"type": "json_object"}
                )
                
                agent_message = response.choices[0].message.content
                messages.append({"role": "assistant", "content": agent_message})
                self.result.add_output(f"Agent: {agent_message}")
                
                # Parse action
                try:
                    action_data = json.loads(agent_message)
                    action_name = action_data.get('action')
                    args = action_data.get('args', {})
                    
                    # Handle return action - stop processing and set final result
                    if action_name == 'return':
                        result = args.get('result', '')
                        self.result.message = result
                        break
                        
                    # Execute other actions and continue
                    result = await self._execute_action(action_name, args)
                    messages.append({"role": "system", "content": f"Action result: {result}"})
                    self.result.add_output(f"Action result: {result}")
                    
                except json.JSONDecodeError:
                    error_msg = "Error: Please respond with valid JSON containing action and args"
                    messages.append({"role": "system", "content": error_msg})
                    self.result.add_output(error_msg)
                    break  # Break on JSON error to avoid infinite loop
                except Exception as e:
                    error_msg = f"Error executing action: {str(e)}"
                    messages.append({"role": "system", "content": error_msg})
                    self.result.add_output(error_msg)
                    break  # Break on any other error to avoid infinite loop
            
        except Exception as e:
            error_msg = f"Agent failed: {str(e)}"
            self.logger.error(error_msg)
            if self.result:
                self.result.success = False
                self.result.message = error_msg
            else:
                self.result = JobResult(success=False, message=error_msg)
    
    async def _execute_action(self, action_name: str, args: Dict[str, Any]) -> str:
        """Execute an action through the registry"""
        from src.interfaces.base import Message
        
        try:
            if action_name not in self.action_registry.actions:
                return f"I don't know how to {action_name}"
                
            handler, spec = self.action_registry.actions[action_name]
            
            # Create message for action
            message = Message(
                session_id=self.session_id,
                content=action_name,
                arguments=[]
            )
            
            # Extract arguments in the order specified by the spec
            action_args = []
            if spec and spec.arguments:
                for arg in spec.arguments:
                    if arg.name in args:
                        action_args.append(args[arg.name])
            
            # Execute action with ordered arguments
            result = await handler(message, *action_args)
            return str(result)
            
        except Exception as e:
            return f"Failed to execute {action_name}: {str(e)}"
        
    async def stop(self) -> None:
        """Stop the agent - no special cleanup needed"""
        pass

class ConversationAgent:
    """Agent that maintains conversation context and can execute actions"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.logger = Logger(f"ConversationAgent-{session_id}")
        self.config = Config()
        
        # Get OpenAI configuration
        try:
            # Use the property accessors
            openai_key = self.config.openai_api_key
            self.client = AsyncOpenAI(api_key=openai_key)
            self.model = self.config.openai_model
            self.logger.info(f"Using OpenAI model: {self.model}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenAI: {e}")
            raise
        
        self.messages: List[Dict[str, str]] = []
        self.action_registry = None  # Lazy load to avoid circular imports
        self.active_jobs = {}  # Track jobs we're waiting for
        
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
            "You have access to:\n"
            "- Smart contract source code from bounties and contests\n"
            "- Active bug bounty programs and their details\n"
            "- Audit contest information and deadlines\n"
            "- On-chain data about deployed contracts\n"
            "- Historical vulnerability reports and fixes\n"
            "- Code patterns and common vulnerabilities\n\n"
            "The data is organized into:\n\n"
            "Projects:\n"
            "- Active bug bounty programs (e.g., from Immunefi)\n"
            "- Smart contract audit contests\n"
            "- Each project has details like rewards, scope, and deadlines\n\n"
            "Assets:\n"
            "- Smart contract source files (Solidity, Cairo, etc.)\n"
            "- GitHub repositories with full codebases\n"
            "- Deployed contracts with verified source code\n"
            "- Documentation and specifications\n"
            "- Historical audit reports and findings\n\n"
            "You can help researchers:\n"
            "- Find high-reward bounty programs\n"
            "- Search for specific vulnerability patterns\n"
            "- Analyze smart contract codebases\n"
            "- Track contest deadlines and updates\n"
            "- Cross-reference similar vulnerabilities\n"
            "- Identify potential security issues\n\n"
            f"Available actions:\n{actions}\n\n"
            "Database Search Examples (all responses must be JSON):\n"
            "1. To find high-value bounties:\n"
            '{"action": "database_search", "args": {"query": "search projects type=immunefi"}}\n\n'
            "2. To find Cairo smart contracts:\n"
            '{"action": "database_search", "args": {"query": "search assets local_path=%.cairo"}}\n\n'
            "3. To list all GitHub repositories:\n"
            '{"action": "database_search", "args": {"query": "search assets type=github_repo"}}\n\n'
            "4. To find deployed contracts:\n"
            '{"action": "database_search", "args": {"query": "search assets type=deployed_contract"}}\n\n'
            "For normal conversation, respond with JSON:\n"
            '{"response": "your message here"}\n\n'
            "Remember:\n"
            "- You MUST ALWAYS respond in valid JSON format\n"
            "- Every single response must be a JSON object\n"
            "- You are a security research assistant focused on finding vulnerabilities\n"
            "- Always think about potential security implications\n"
            "- Suggest relevant vulnerability patterns to look for\n"
            "- Help prioritize high-value targets\n"
            "- The database_search action requires a specific format:\n"
            "  - For counting: count <target>\n"
            "  - For searching: search <target> [filters]\n"
            "  - Available targets: projects, assets\n"
            "  - Available asset types: github_repo, github_file, deployed_contract\n"
            "- Keep track of context and suggest relevant follow-up searches\n"
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
            
    async def _execute_action(self, action_name: str, args: Dict[str, Any]) -> str:
        """Execute an action through the registry"""
        from src.interfaces.base import Message
        
        try:
            if action_name not in self.action_registry.actions:
                return f"I don't know how to {action_name}"
                
            handler, spec = self.action_registry.actions[action_name]
            
            # Create message for action
            message = Message(
                session_id=self.session_id,
                content=action_name,
                arguments=[]
            )
            
            # Extract arguments in the order specified by the spec
            action_args = []
            if spec and spec.arguments:
                for arg in spec.arguments:
                    if arg.name in args:
                        action_args.append(args[arg.name])
            
            # Execute action with ordered arguments
            result = await handler(message, *action_args)
            return str(result)
            
        except Exception as e:
            return f"Failed to execute {action_name}: {str(e)}"
        