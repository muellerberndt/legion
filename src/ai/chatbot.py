"""Chatbot implementation using the new chat_completion function"""

from typing import Dict, List, Any
import json
from src.config.config import Config
from src.util.logging import Logger
from src.actions.registry import ActionRegistry
from src.ai.llm import chat_completion
from src.util.command_parser import CommandParser
from datetime import datetime
import re


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
        base_prompt = (
            f"{personality}\n\n"
            "Additional instructions:\n"
            "1. Do not lie or make up facts.\n"
            "2. If a user messages you in a foreign language, please respond in that language.\n"
            "3. Do not use markdown or HTML tags in your responses.\n"
            "4. Always specify the language in code blocks.\n"
        )

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

    def _truncate_result(self, result: str, max_length: int = 4000) -> str:
        """Truncate a result string to a reasonable size"""
        if len(result) <= max_length:
            return result

        # For JSON strings, try to parse and truncate the content
        try:
            data = json.loads(result)
            if isinstance(data, dict):
                if "results" in data and isinstance(data["results"], list):
                    # Truncate results array
                    original_count = len(data["results"])
                    data["results"] = data["results"][:10]  # Keep only first 10 results
                    data["note"] = f"Results truncated to 10 of {original_count} total matches"
                return json.dumps(data, indent=2)  # Pretty print JSON
        except json.JSONDecodeError:
            pass

        # For plain text, truncate with ellipsis
        return result[:max_length] + "... (truncated)"

    def _format_response(self, text: str) -> str:
        """Format response text to be safe for Telegram"""
        # Remove any special characters that could cause parsing issues
        text = text.replace("`", "").replace("*", "").replace("_", "")

        # For JSON responses, format them cleanly
        if text.startswith("{") and text.endswith("}"):
            try:
                data = json.loads(text)
                # Format without special characters
                return json.dumps(data, indent=2, ensure_ascii=True)
            except json.JSONDecodeError:
                pass

        return text

    def _add_to_history(self, role: str, content: str) -> None:
        """Add a message to conversation history"""
        self.history.append({"role": role, "content": content})

        # Keep history within limits, but preserve system message
        if len(self.history) > self.max_history + 1:  # +1 for system message
            # Remove oldest messages but keep system message
            self.history = [self.history[0]] + self.history[-(self.max_history) :]

    async def execute_command(self, command: str, param_str: str, update_callback=None) -> str:
        """Execute a registered command"""
        # Remove preceding slash
        command = command.lstrip("/")

        # Handle empty command case for conclusion
        if not command:
            return "Command completed successfully"

        if command not in self.commands:
            raise ValueError(f"Unknown command: {command}")

        self.logger.info(f"Executing command: {command} with params: {param_str}")

        # Get command spec and handler
        action = self.action_registry.get_action(command)
        if not action:
            raise ValueError(f"Action not found for command: {command}")
        handler, spec = action

        try:
            # Parse and validate arguments
            if isinstance(param_str, list):
                # If we already have a list of parameters, use them directly
                args = param_str
            else:
                # Parse arguments
                args = self.command_parser.parse_arguments(param_str, spec)

            self.command_parser.validate_arguments(args, spec)

            # Execute the command
            if isinstance(args, dict):
                result = await handler(**args)
            else:
                result = await handler(*args)

            # For autobot command, return the result directly without error checking
            if command == "autobot":
                return result

            # Check if this is a job result
            if isinstance(result, str):
                # Look for job ID patterns
                job_patterns = [
                    r"[Jj]ob (?:ID: )?([a-f0-9-]+)",
                    r"[Jj]ob_id: ([a-f0-9-]+)",
                    r"[Ss]tarted.*[Jj]ob.*?([a-f0-9-]+)",
                ]

                for pattern in job_patterns:
                    match = re.search(pattern, result)
                    if match:
                        job_id = match.group(1)
                        return f"Started job {job_id}\nUse /job {job_id} to check results"

            return result

        except Exception as e:
            self.logger.error(f"Error executing command: {str(e)}")
            raise

    async def _plan_next_step(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """Plan the next step based on current state"""
        try:
            # For complex queries requiring commands, proceed with planning
            messages = [
                {"role": "system", "content": self.system_prompt},
                {
                    "role": "system",
                    "content": """Plan and execute tasks using the available commands.

Your response MUST be a valid JSON object with these fields:
{
    "thought": "Your internal reasoning about what to do next",
    "command": "command_name param1 param2 (...)",
    "output": "The message to show to the user",
    "is_final": boolean (true if this is your final response)
}

The "output" field will be shown directly to the user, so it should be properly formatted.
For intermediate steps (is_final=false), you can leave "output" empty.

CRITICAL INSTRUCTIONS:
1. For complex tasks that require multiple steps or jobs, use the /autobot command to delegate the task.
2. For tasks involving file searching, analysis, or multiple steps, ALWAYS use the /autobot command.
3. NEVER truncate your output. Show ALL results completely.
4. Do not add notes like "(truncated)" or "for brevity".
5. When formatting lists or results, include ALL items with their complete information.

Example responses:

For simple tasks:
{
    "thought": "I need to get the list of projects from the database",
    "command": "db_query '{\"from\": \"projects\", \"limit\": 5}'",
    "output": "",
    "is_final": false
}

For complex tasks:
{
    "thought": "This task requires multiple search and database commands. I should delegate it to an autobot.",
    "command": "autobot \"Search for files containing 'bla bla', then retrieve the project information for each match and summarize the results\"",
    "output": "",
    "is_final": true
}

IMPORTANT:
1. Return ONLY the JSON object, no other text
2. Use double quotes for strings
3. Use true/false (lowercase) for booleans
4. If using a command, it must be one of the available commands
5. Arguments containing spaces must be quoted!
6. NEVER truncate or omit information from results
7. For complex tasks requiring multiple steps, ALWAYS use the /autobot command

Available commands and their parameters:"""
                    + "\n"
                    + "\n".join(
                        f"- {name}: {cmd.description}\n  Parameters: {', '.join(arg.name + ('*' if arg.required else '') for arg in cmd.arguments)}"
                        for name, cmd in self.commands.items()
                    )
                    + "\n",
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

            # Only validate command if it's not empty
            if plan["command"].strip():
                # Extract command name and validate it exists
                command_parts = plan["command"].split(maxsplit=1)
                command_name = command_parts[0]
                if command_name not in self.commands:
                    raise ValueError(f"Unknown command: {command_name}. Must be one of: {', '.join(self.commands.keys())}")

            return plan

        except Exception as e:
            self.logger.error(f"Error planning next step: {str(e)}")
            raise

    async def process_message(self, message: str, update_callback=None) -> str:
        """Process a user message and return a response"""
        try:
            # Add user message to history
            self._add_to_history("user", message)

            # Initialize state
            state = {"task": {"prompt": message, "timestamp": datetime.utcnow().isoformat()}, "status": "started"}

            # Check if this is a direct command invocation
            if message.startswith("/"):
                command, args_str = self.command_parser.parse_command(message)
                if command in self.commands:
                    try:
                        # Execute the command directly
                        result = await self.execute_command(command, args_str)
                        # For autobot command, don't show error messages
                        if command == "autobot" and "error" in result.lower():
                            return ""
                        result = self._truncate_result(str(result))
                        formatted_response = self._format_response(result)
                        self._add_to_history("assistant", formatted_response)
                        return formatted_response
                    except Exception as e:
                        error_msg = f"Error executing command: {str(e)}"
                        self.logger.error(error_msg)
                        # For autobot command, don't show error messages
                        if command == "autobot":
                            return ""
                        return self._format_response(error_msg)

            # For non-command messages, proceed with multi-step execution
            max_steps = 10
            step_count = 0

            while True:
                # Check step limit
                if step_count >= max_steps:
                    error_msg = f"Task exceeded maximum steps ({max_steps})"
                    self.logger.error(error_msg)
                    return self._format_response(error_msg)

                # Plan next step
                plan = await self._plan_next_step(state)

                # Handle empty command (direct response)
                if not plan["command"].strip():
                    # For final steps, return the formatted result
                    if plan["is_final"]:
                        # Add to history and return
                        self._add_to_history("assistant", plan["output"])
                        return self._format_response(plan["output"])
                    else:
                        # For non-final direct responses, continue to next step
                        state["last_result"] = plan["output"]
                        step_count += 1
                        continue

                # For command execution, show step info
                if update_callback:
                    step_info = []
                    if plan["thought"]:
                        # Remove any special characters from thought
                        thought = plan["thought"].replace("`", "").replace("'", "").replace('"', "")
                        step_info.append(f"🤔 Thinking: {thought}")
                    if plan["command"].strip():
                        # Extract command name and parameters
                        cmd_parts = plan["command"].split(maxsplit=1)
                        cmd_name = cmd_parts[0]
                        cmd_params = cmd_parts[1] if len(cmd_parts) > 1 else ""

                        # Try to parse and format JSON parameters if present
                        try:
                            if cmd_params.strip().startswith("{"):
                                params_obj = json.loads(cmd_params)
                                # Format JSON without special characters
                                cmd_params = json.dumps(params_obj, separators=(",", ":"), ensure_ascii=True)
                        except Exception:
                            # If JSON parsing fails, just use the original string
                            # Remove any special characters
                            cmd_params = cmd_params.replace("`", "").replace("'", "").replace('"', "")

                        step_info.append(f"🏃 Running: {cmd_name} {cmd_params}")
                    if step_info:
                        await update_callback("\n".join(step_info))

                # Split command into name and parameters
                command_parts = plan["command"].split(maxsplit=1)
                command = command_parts[0]
                param_str = command_parts[1] if len(command_parts) > 1 else ""

                try:
                    # Execute the command
                    result = await self.execute_command(command, param_str)
                    self.logger.info(f"Command result: {result}")

                    # Update state
                    state["last_result"] = result
                    state["is_final"] = plan["is_final"]

                    # For final steps after a command, use the output as the formatted result
                    if plan["is_final"]:
                        state["result"] = plan["output"]
                        state["status"] = "completed"
                        self._add_to_history("assistant", plan["output"])
                        return self._format_response(plan["output"])

                    # For non-final steps, continue to next step
                    step_count += 1

                except Exception as e:
                    error_msg = f"Error executing command: {str(e)}"
                    self.logger.error(error_msg)
                    return self._format_response(error_msg)

        except Exception as e:
            self.logger.error(f"Error processing message: {str(e)}")
            return self._format_response(f"Error processing message: {str(e)}")
