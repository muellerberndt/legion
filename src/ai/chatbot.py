"""Chatbot implementation using the new chat_completion function"""

from typing import Dict, List, Any, Optional
import json
from src.util.logging import Logger
from src.actions.registry import ActionRegistry
from src.ai.llm import chat_completion
from src.util.command_parser import CommandParser
from src.actions.result import ActionResult, ResultType
from src.jobs.manager import JobManager
from src.config.config import Config


class Chatbot:
    """Chatbot that maintains conversation history and can execute commands"""

    def __init__(
        self,
        action_registry: Optional[ActionRegistry] = None,
        custom_prompt: Optional[str] = None,
        command_names: Optional[List[str]] = None,
        max_history: int = 10,
        max_steps: int = 10,
        timeout: int = 300,
    ):
        self.logger = Logger(self.__class__.__name__)
        self.max_history = max_history
        self.max_steps = max_steps
        self.timeout = timeout
        self.config = Config()

        # Use provided action registry or create new one
        self.action_registry = action_registry or ActionRegistry()
        if not action_registry:
            self.logger.debug("Initializing new ActionRegistry")
            self.action_registry.initialize()

        # Get available commands
        self.logger.debug("Getting command instructions")
        self.commands = self.action_registry._get_agent_command_instructions()
        self.logger.debug(f"Got commands: {self.commands}")

        if command_names:
            self.commands = {name: cmd for name, cmd in self.commands.items() if name in command_names}

        self.command_parser = CommandParser()

        # Build system prompt using personality from config
        self.system_prompt = custom_prompt or self.config.get("llm.personality", "Research assistant of a web3 bug hunter.\n")

        # Add command instructions to system prompt
        self.system_prompt += "Available commands:\n\n"
        for name, cmd in self.commands.items():
            self.system_prompt += f"/{name}: {cmd.description}\n"
            if cmd.help_text:
                self.system_prompt += f"  {cmd.help_text}\n"
            if cmd.agent_hint:
                self.system_prompt += f"  Hint: {cmd.agent_hint}\n"
            self.system_prompt += "\n"

        # Initialize conversation history with system prompt
        self.history = [{"role": "system", "content": self.system_prompt}]

    def _add_to_history(self, role: str, content: str) -> None:
        """Add a message to conversation history"""
        self.history.append({"role": role, "content": content})

        # Keep history within limits, but preserve system message
        if len(self.history) > self.max_history + 1:  # +1 for system message
            # Remove oldest messages but keep system message
            self.history = [self.history[0]] + self.history[-(self.max_history) :]

        # Check total token usage and trim if needed
        _, _, available = self.get_context_limits()
        current_tokens = sum(self.count_tokens(msg["content"]) for msg in self.history)

        if current_tokens > available:
            # Always keep system message and last 2 messages of conversation
            preserved = [self.history[0]] + self.history[-2:]
            older_messages = self.history[1:-2]

            # Remove older messages until we're under the limit
            while current_tokens > available and older_messages:
                removed = older_messages.pop()
                current_tokens -= self.count_tokens(removed["content"])

            # Reconstruct history with remaining messages
            self.history = preserved if not older_messages else [self.history[0]] + older_messages + self.history[-2:]

    def count_tokens(self, text: str) -> int:
        """Estimate token count for a string"""
        # Rough estimation: 4 chars per token
        return len(text) // 4

    def get_context_limits(self) -> tuple[int, int, int]:
        """Get context limits from config"""
        max_tokens = self.config.get("llm.openai.max_context_length", 128000)
        reserve = self.config.get("llm.openai.context_reserve", 8000)
        available = max_tokens - reserve
        return max_tokens, reserve, available

    def get_available_space(self) -> int:
        """Calculate remaining available space"""
        _, _, total_available = self.get_context_limits()
        used = sum(self.count_tokens(msg["content"]) for msg in self.history)
        return max(0, total_available - used)

    def _truncate_result(self, result: str) -> str:
        """Dynamically truncate results based on available space"""
        available_space = self.get_available_space()

        # Use up to 25% of available space for results, but no more than 1/8 of total context
        max_tokens, _, _ = self.get_context_limits()
        max_result_tokens = min(
            available_space // 4, max_tokens // 8  # 25% of available space  # Or 1/8 of total context, whichever is smaller
        )

        result_tokens = self.count_tokens(result)
        if result_tokens <= max_result_tokens:
            return result

        # If JSON, try to preserve structure while truncating
        try:
            data = json.loads(result)
            if isinstance(data, dict):
                # Truncate each field intelligently
                truncated = {}
                for k, v in data.items():
                    if isinstance(v, list):
                        truncated[k] = v[:10]  # Keep first 10 items
                    elif isinstance(v, str) and len(v) > 100:
                        truncated[k] = v[:100] + "..."
                    else:
                        truncated[k] = v
                return json.dumps(truncated)
        except json.JSONDecodeError:
            pass

        # For plain text, preserve beginning and end with context
        if result_tokens > max_result_tokens:
            # Keep first 2/3 and last 1/3 of allowed size
            chars_to_keep = max_result_tokens * 4  # Convert tokens to chars
            first_part = int(chars_to_keep * 0.67)
            last_part = int(chars_to_keep * 0.33)

            return f"{result[:first_part]}\n...[truncated]...\n{result[-last_part:]}"

    async def execute_command(self, command: str, args_str: str, update_callback=None) -> ActionResult:
        """Execute a command with the given arguments"""
        try:
            # Get the action handler
            action = self.action_registry.get_action(command)
            if not action:
                raise ValueError(f"Unknown command: {command}")

            handler, spec = action

            # Parse and validate arguments
            args = self.command_parser.parse_arguments(args_str, spec)
            self.command_parser.validate_arguments(args, spec)

            # Execute the command with update callback
            result = await handler(*args, _update_callback=update_callback)

            # If this is a job result, wait for completion
            if isinstance(result, ActionResult) and result.type == ResultType.JOB:
                self.logger.info(f"Waiting for job {result.job_id} to complete")
                job_manager = await JobManager.get_instance()
                job_result = await job_manager.wait_for_job_result(result.job_id)
                if job_result:
                    return ActionResult.text(self._truncate_result(job_result.get_output()))
                return ActionResult.text("No output available")

            if not isinstance(result, ActionResult):
                raise ValueError(f"Action {command} returned {type(result)}, expected ActionResult")

            # Truncate any result type after converting to string
            return ActionResult.text(self._truncate_result(str(result)))

        except Exception as e:
            self.logger.error(f"Error executing command: {str(e)}")
            raise

    async def _plan_next_step(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """Plan the next step based on current state"""
        try:
            # Include full conversation history
            messages = self.history.copy()  # Start with existing history

            # Add the result handling instructions
            messages.append(
                {
                    "role": "system",
                    "content": """Legion is an AI-driven framework that automates web3 bug hunting workflows.
It collects and correlates data from bug bounty programs, audit contests, and on-chain and off-chain sources.
User requests, event triggers, and scheduled tasks spawn agents that execute commands to perform tasks.
As the Legion chatbot, you are the interface between the user and the framework.
You execute commands on behalf of the user so they can focus on planning and thinking.

Plan and execute tasks using the available commands.

Your response MUST be a valid JSON object with these fields:
{
    "thought": "Your internal reasoning about what to do next",
    "command": "command_name param1 param2 (...)",
    "output": "The message to show to the user",
    "is_final": boolean (true if this is your final response)
}

FORMATTING RULES (STRICTLY ENFORCED):
1. PLAIN TEXT ONLY - NO markdown, NO HTML, NO special formatting
2. Use this format for lists:
   🔍 Found X items:

   1. Name (Context) - Description
      → address or link

   2. Name (Context) - Description
      → address or link

3. Use emojis for headers (🔍, ℹ️)
4. Use → for links/addresses
5. Use plain numbers and spaces for structure

CRITICAL INSTRUCTIONS:

1. NEVER truncate your output. Show ALL results completely.
2. When formatting lists or results, include ALL items with their complete information.
3. Try to be efficient - use as few database queries as possible.
4. DO NOT use markdown or HTML tags in your responses.
5. ALWAYS set is_final to true when you have all the information needed to answer the user's question.
6. NEVER repeat the same command without a different purpose.
7. If you have the information needed, format it and return it immediately with is_final=true.
8. Track what information you've already gathered in your thought process.
9. For database queries, try to get all needed information in a single query using JOINs when possible.
10. If you find yourself wanting to repeat a command, stop and format what you already have.
11. Always quote command arguments.

RESULT HANDLING INSTRUCTIONS:

1. For commands that return raw data that the user explicitly requested, return the results directly:
   - /get_code: Return the code directly when user asks for code

2. For commands that return metadata or require interpretation, summarize the results:
   - Database queries that return project/asset information
   - Status updates
   - Job results that need explanation

3. For commands that return lists, tables or tree structures, format them concisely for the Telegram UI.

Example for list formatting:

🔍 Found 10 finalize functions:

1. finalizeBridgeERC721 (Optimism) - ERC721 token bridge finalization
   → 0x3268ed09f76e619331528270b6267d4d2c5ab5c2

2. finalizeBridgeETH (Optimism) - ETH bridge transfers
   → 0xae2af01232a6c4a4d3012c5ec5b1b35059caf10d

Examples:

Good (direct code request):
User: "Show me the code for asset X"
{
    "thought": "User wants the raw code, I'll return it directly",
    "command": "get_code 123",
    "output": "",
    "is_final": true
}

Good (metadata query):
User: "What's the latest asset?"
{
    "thought": "Need to query and summarize the asset info",
    "command": "db_query '...'",
    "output": "",
    "is_final": false
}
// After command executes, summarize the result
{
    "thought": "Summarizing the asset information",
    "command": "",
    "output": "The latest asset is X from project Y, added on date Z",
    "is_final": true
}

User: "Find me functions in bridge smart contracts that finalize transactions"
// Execute the command first, then format the result for the user
{
    "thought": "I'll format the list of finalize functions in a clear, plain text format with emojis for better readability",
    "command": "",
    "output": "🔍 Found 10 finalize functions:\n\n1. finalizeBridgeERC721 (Optimism) - ERC721 token bridge finalization\n   → 0x3268ed09f76e619331528270b6267d4d2c5ab5c2\n\n2. finalizeBridgeETH (Optimism) - ETH bridge transfers\n   → 0xae2af01232a6c4a4d3012c5ec5b1b35059caf10d\n\n3. finalizeBridgeERC721 (Optimism) - ERC721 cross-bridge transfers\n   → 0xc599fa757c2bcaa5ae3753ab129237f38c10da0b",
    "is_final": true
}
""",
                }
            )

            # Add current state
            messages.append({"role": "user", "content": f"Current state: {json.dumps(current_state, indent=2)}"})

            # Get response from LLM
            response = await chat_completion(messages)

            # Clean up response - remove any markdown and whitespace
            cleaned_response = response.strip()
            if "```" in cleaned_response:
                # Extract content between code blocks if present
                parts = cleaned_response.split("```")
                for part in parts:
                    if "{" in part and "}" in part:
                        cleaned_response = part.strip()
                        break

            # Remove any "json" or other language indicators
            if cleaned_response.startswith("json"):
                cleaned_response = cleaned_response[4:].strip()

            # Parse response as JSON
            try:
                plan = json.loads(cleaned_response)
            except json.JSONDecodeError as e:
                self.logger.error(f"Invalid JSON response from LLM: {cleaned_response}")
                self.logger.error(f"JSON parse error: {str(e)}")
                raise ValueError(f"Failed to parse LLM response as JSON: {str(e)}")

            # Validate required fields
            required_fields = ["thought", "command", "output", "is_final"]
            missing = [field for field in required_fields if field not in plan]
            if missing:
                raise ValueError(f"Missing required fields in plan: {missing}")

            # Validate field types
            if not isinstance(plan["thought"], str):
                raise ValueError("Field 'thought' must be a string")
            if not isinstance(plan["command"], str):
                raise ValueError("Field 'command' must be a string")
            if not isinstance(plan["output"], str):
                raise ValueError("Field 'output' must be a string")
            if not isinstance(plan["is_final"], bool):
                raise ValueError("Field 'is_final' must be a boolean")

            # Add loop detection
            if "command_history" not in current_state:
                current_state["command_history"] = []

            # Check for command repetition
            if plan["command"].strip():
                if plan["command"] in current_state["command_history"]:
                    self.logger.warning("Command repetition detected, forcing final response")
                    return {
                        "thought": "Detected command repetition. Formatting available information.",
                        "command": "",
                        "output": f"Based on the information gathered so far: {current_state.get('last_result', 'No results available')}",
                        "is_final": True,
                    }
                current_state["command_history"].append(plan["command"])

            # Only validate command if it's not empty
            if plan["command"].strip():
                # Extract command name and validate it exists
                command_parts = plan["command"].split(maxsplit=1)
                command_name = command_parts[0].lstrip("/")  # Strip leading slash - ensure only one slash is removed
                if command_name not in self.commands:
                    raise ValueError(f"Unknown command: {command_name}. Must be one of: {', '.join(self.commands.keys())}")

            return plan

        except Exception as e:
            self.logger.error(f"Error planning next step: {str(e)}")
            raise

    async def process_message(self, message: str, update_callback=None, action_callback=None) -> str:
        """Process a message and return a response"""
        try:
            # Initialize state
            state = {
                "message": message,
                "status": "in_progress",
                "result": None,
                "last_result": None,
                "command_history": [],
                "is_final": False,
            }

            # Add message to history
            self._add_to_history("user", message)

            # Process message in steps
            steps = 0
            while steps < self.max_steps and not state["is_final"]:
                steps += 1

                # Get next action from LLM
                plan = await self._plan_next_step(state)

                # Only show thoughts if we're about to execute a command
                if update_callback and plan.get("command") and plan.get("thought"):
                    await update_callback(f"🤔 {plan['thought']}")

                # If there's a command to execute
                if plan["command"].strip():
                    command, args_str = self.command_parser.parse_command(plan["command"])

                    # Check for command repetition
                    if command in state["command_history"]:
                        if state["last_result"] is not None:
                            state["is_final"] = True
                            state["result"] = f"Based on the information gathered so far: {str(state['last_result'])}"
                            return state["result"]
                        else:
                            state["command_history"] = []  # Reset history to allow retry

                    try:
                        # Show command being executed if callback provided
                        if update_callback:
                            await update_callback(f"🛠️ Executing: {plan['command']}")

                        result = await self.execute_command(command, args_str)
                        # Convert ActionResult to string when storing in state
                        state["last_result"] = str(result)

                        # Call action_callback if provided
                        if action_callback:
                            await action_callback(plan["command"], result)

                        # Record the command and its result in history
                        state["command_history"].append(command)
                        self._add_to_history("assistant", f"Command executed: /{plan['command']}\nResult: {str(result)}")

                    except Exception as e:
                        self.logger.error(f"Error executing command: {str(e)}")
                        state["last_result"] = f"Error: {str(e)}"
                        self._add_to_history("assistant", f"Command failed: /{plan['command']}\nError: {str(e)}")

                # Update state
                state["is_final"] = plan["is_final"]
                if plan["is_final"]:
                    state["result"] = plan["output"]
                    state["status"] = "completed"

                # For final response, record in history and return
                if plan["is_final"]:
                    self._add_to_history("assistant", plan["output"])
                    return plan["output"]

            return state.get("result", "No response generated")

        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            self.logger.error(error_msg)
            self._add_to_history("assistant", error_msg)
            return error_msg
