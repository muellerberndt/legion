"""Chatbot implementation using the new chat_completion function"""

from typing import Dict, List, Any
import json
from src.config.config import Config
from src.util.logging import Logger
from src.actions.registry import ActionRegistry
from src.ai.llm import chat_completion
from src.util.command_parser import CommandParser
from src.actions.result import ActionResult, ResultType
from src.jobs.manager import JobManager


class Chatbot:
    """Chatbot that maintains conversation history and can execute commands"""

    def __init__(self, max_history: int = 10):
        self.logger = Logger("Chatbot")
        self.config = Config()
        self.action_registry = ActionRegistry()
        self.action_registry.initialize()
        self.command_parser = CommandParser()

        # Get all available commands
        self.commands = self.action_registry._get_agent_command_instructions(include_all=True)
        self.logger.info("Initialized with commands:", extra_data={"commands": list(self.commands.keys())})

        # Build system prompt
        personality = self.config.get("llm.personality")
        base_prompt = f"{personality}\n\n"

        # Add command descriptions
        command_descriptions = []
        for name, cmd in self.commands.items():
            # Build parameter string
            params = []
            if cmd.arguments:
                for arg in cmd.arguments:
                    if arg.required:
                        params.append(f"<{arg.name}>")
                    else:
                        params.append(f"[{arg.name}]")

            param_str = " ".join(params)

            # Build command description with help text and agent hint
            command_desc = [f"/{name} {param_str}", cmd.description]

            if cmd.help_text:
                command_desc.append(f"Help: {cmd.help_text}")
            if cmd.agent_hint:
                command_desc.append(f"Usage hint: {cmd.agent_hint}")

            command_descriptions.append("\n".join(command_desc))

        if command_descriptions:
            base_prompt += "\n\nAvailable commands:\n\n" + "\n\n".join(command_descriptions)

        self.system_prompt = base_prompt

        # Initialize conversation history
        self.max_history = max_history
        self.history: List[Dict[str, str]] = [{"role": "system", "content": self.system_prompt}]

    def _truncate_result(self, result: str, max_length: int = 4000) -> tuple[str, str | None]:
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
                        return truncated, result  # Return original result as full content
        except json.JSONDecodeError:
            pass

        # For plain text, truncate with ellipsis
        truncated = result[:max_length] + "... (truncated)"
        return truncated, result  # Return original result as full content

    def _add_to_history(self, role: str, content: str) -> None:
        """Add a message to conversation history"""
        self.history.append({"role": role, "content": content})

        # Keep history within limits, but preserve system message
        if len(self.history) > self.max_history + 1:  # +1 for system message
            # Remove oldest messages but keep system message
            self.history = [self.history[0]] + self.history[-(self.max_history) :]

    async def execute_command(self, command: str, args_str: str, update_callback=None) -> Any:
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
            if isinstance(result, ActionResult):
                if result.type == ResultType.JOB:
                    self.logger.info(f"Waiting for job {result.job_id} to complete")
                    job_manager = await JobManager.get_instance()
                    job_result = await job_manager.wait_for_job_result(result.job_id)
                    return job_result
                else:
                    # For non-job ActionResults, get the content
                    return result.content if result.content is not None else str(result)

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

    async def process_message(self, message: str, update_callback=None) -> str:
        """Process a natural language message and return a response"""
        try:
            # Record user message
            self._add_to_history("user", message)

            # Initialize state for this message
            state = {
                "message": message,
                "last_result": None,
                "status": "started",
                "is_final": False,
                "context": {},  # Add persistent context
                "command_history": [],
            }

            # Load context from previous messages in history
            for msg in self.history:
                if msg["role"] == "assistant" and "Command executed:" in msg["content"]:
                    # Extract command and result
                    cmd_result = msg["content"].split("\nResult: ", 1)
                    if len(cmd_result) == 2:
                        cmd, result = cmd_result
                        # Store query results in context
                        if "db_query" in cmd:
                            state["context"]["last_query_result"] = result

            # Use AI planning
            while not state["is_final"]:
                # Get next step from AI
                plan = await self._plan_next_step(state)

                # Show AI's thought process if callback provided
                if update_callback and plan["thought"].strip():
                    await update_callback(f"🤔 {plan['thought']}")

                # If there's a command to execute
                if plan["command"].strip():
                    command, args_str = self.command_parser.parse_command(plan["command"])
                    try:
                        # Show command being executed if callback provided
                        if update_callback:
                            await update_callback(f"🛠️ Executing: /{plan['command']}")

                        result = await self.execute_command(command, args_str, update_callback=update_callback)
                        state["last_result"] = result

                        # Record the command and its result in history
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
