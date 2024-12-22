"""Chatbot implementation using the new chat_completion function"""

from typing import Dict, List, Any, Optional, Tuple
import json
from src.util.logging import Logger
from src.actions.registry import ActionRegistry
from src.ai.llm import chat_completion
from src.util.command_parser import CommandParser
from src.actions.result import ActionResult, ResultType
from src.jobs.manager import JobManager


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

        # Build system prompt
        self.system_prompt = custom_prompt or "Research assistant of a web3 bug hunter.\n"
        self.system_prompt += "You are a web3 soldier and the user is your commander. Use military language and 🫡 emoji!\n"
        self.system_prompt += 'Unironcially use terms like "ser", "gm", "wagmi", "chad", "based".\n'
        self.system_prompt += "Often compliment the user on their elite security researcher status.\n\n"

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

    def _truncate_result(self, result: str, max_length: int = 4000) -> Tuple[str, Optional[str]]:
        """Truncate a result string and return both truncated text and full content if truncated"""
        if len(result) <= max_length:
            return result, None

        # For JSON strings, try to parse and truncate the content
        try:
            data = json.loads(result)
            if isinstance(data, dict):
                if "results" in data and isinstance(data["results"], list):
                    # Truncate results array
                    original_count = len(data["results"])
                    data["results"] = data["results"][:10]  # Keep only first 10 results
                    data["note"] = f"Results truncated to 10 of {original_count} total matches"
                    truncated = json.dumps(data, indent=2)
                    if len(truncated) <= max_length:
                        return truncated, result
        except json.JSONDecodeError:
            pass

        # For plain text, truncate with ellipsis
        truncated = result[:max_length] + "... (truncated)"
        return truncated, result

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
                    return ActionResult.text(job_result.get_output())
                return ActionResult.text("No output available")

            if not isinstance(result, ActionResult):
                raise ValueError(f"Action {command} returned {type(result)}, expected ActionResult")

            return result

        except Exception as e:
            self.logger.error(f"Error executing command: {str(e)}")
            raise

    async def _plan_next_step(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """Plan the next step based on current state"""
        try:
            # Add instruction about result handling
            messages = [
                {"role": "system", "content": self.system_prompt},
                {
                    "role": "system",
                    "content": """
Legion is an AI-driven framework that automates web3 bug hunting workflows.
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

CRITICAL INSTRUCTIONS:

1. NEVER truncate your output. Show ALL results completely.
2. When formatting lists or results, include ALL items with their complete information.
3. Try to be efficient - use as few database queries as possible.
4. Do NOT use markdown or HTML tags in your responses.
5. ALWAYS set is_final to true when you have all the information needed to answer the user's question.
6. NEVER repeat the same command without a different purpose.
7. If you have the information needed, format it and return it immediately with is_final=true.
8. Track what information you've already gathered in your thought process.
9. For database queries, try to get all needed information in a single query using JOINs when possible.
10. If you find yourself wanting to repeat a command, stop and format what you already have.

RESULT HANDLING INSTRUCTIONS:

1. For commands that return raw data that the user explicitly requested, pass through the result directly:
   - /get_code: Return the code directly when user asks for code
   - /file_search: Return the matches directly when user searches for specific patterns
   - /semantic_search: Return the search results directly

2. For commands that return metadata or require interpretation, summarize the results:
   - Database queries that return project/asset information
   - Status updates
   - Job results that need explanation

Examples:

Good (direct code request):
User: "Show me the code for asset X"
{
    "thought": "User wants the raw code, I'll return it directly",
    "command": "get_code 123",
    "output": "",
    "is_final": false
}
// After command executes, return the code directly
{
    "thought": "Returning the code directly as requested",
    "command": "",
    "output": "<the raw code>",
    "is_final": true
}

Good (metadata query):
User: "What's the latest asset?"
{
    "thought": "Need to query and summarize the asset info",
    "command": "db_query ...",
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
""",
                },
                {"role": "user", "content": f"Current state: {json.dumps(current_state, indent=2)}"},
            ]

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

                # Show AI's thought process if callback provided
                if update_callback and plan.get("thought"):
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
                            await update_callback(f"🛠️ Executing: /{plan['command']}")

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
