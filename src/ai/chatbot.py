"""Chatbot implementation using the new chat_completion function"""

from typing import Dict, List
import json
import html
from src.config.config import Config
from src.util.logging import Logger
from src.actions.registry import ActionRegistry
from src.ai.llm import chat_completion
from src.util.command_parser import CommandParser


class Chatbot:
    """Chatbot that maintains conversation history and can execute commands"""

    def __init__(self, max_history: int = 10):
        self.logger = Logger("Chatbot")
        self.config = Config()
        self.action_registry = ActionRegistry()
        self.action_registry.initialize()
        self.command_parser = CommandParser()

        # Get all available commands
        self.commands = self.action_registry._get_agent_command_instructions()
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
        # Escape any HTML-like characters
        text = html.escape(text)

        # Format code blocks and JSON
        if text.startswith("{") and text.endswith("}"):
            try:
                # Try to parse and pretty print JSON
                data = json.loads(text)
                return f"```\n{json.dumps(data, indent=2)}\n```"
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

    async def execute_command(self, command: str, param_str: str) -> str:
        """Execute a registered command"""
        # Remove preceding slash
        command = command.lstrip("/")

        # Handle empty command case for conclusion
        if not command:
            return self.get_execution_summary()

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

            return result

        except Exception as e:
            self.logger.error(f"Error executing command: {str(e)}")
            raise

    async def process_message(self, message: str) -> str:
        """Process a user message and return a response"""
        try:
            # Add user message to history
            self._add_to_history("user", message)

            # Check if this is a direct command invocation
            if message.startswith("/"):
                command, args_str = self.command_parser.parse_command(message)
                if command in self.commands:
                    try:
                        # Execute the command directly
                        result = await self.execute_command(command, args_str)
                        result = self._truncate_result(str(result))
                        formatted_response = self._format_response(result)
                        self._add_to_history("assistant", formatted_response)
                        return formatted_response
                    except Exception as e:
                        error_msg = f"Error executing command: {str(e)}"
                        self.logger.error(error_msg)
                        return self._format_response(error_msg)

            # For non-command messages, proceed with LLM processing
            plan = await chat_completion(
                self.history
                + [
                    {
                        "role": "system",
                        "content": """Determine if this message requires executing any commands.
For casual conversation or greetings, just respond naturally.
Only suggest commands if the user is asking for specific information or actions.

IMPORTANT: You can only execute ONE command at a time. If you need multiple queries, execute the most relevant one first and wait for the result.

Database schema:
- projects table: Contains project information (id, name, project_type, etc.)
  keywords field is a JSON array of strings
- assets table: Contains assets (id, asset_type, source_url, etc.)
- project_assets table: Association table linking projects and assets (project_id, asset_id)
  project_assets.project_id references projects.id
  project_assets.asset_id references assets.id

If a command is needed, respond with exactly:
EXECUTE: command_name param1 param2 (...)
For casual chat: Just respond normally

Do not try to execute multiple commands or modify queries based on previous results. Execute one command and wait for the response.
Do not use HTML formatting in your responses.""",
                    }
                ]
            )

            # For casual conversation, add response to history and return
            if "EXECUTE:" not in plan:
                formatted_response = self._format_response(plan)
                self._add_to_history("assistant", formatted_response)
                return formatted_response

            # Extract and execute the command
            command_line = plan.split("EXECUTE:", 1)[1].strip()
            self.logger.info(f"Processing command: {command_line}")

            # Parse command and parameters
            parts = command_line.split(" ", 1)
            command = parts[0]
            params_str = parts[1].strip() if len(parts) > 1 else ""

            try:
                # Execute the command
                result = await self.execute_command(command, params_str)

                # Truncate large results
                result = self._truncate_result(str(result))

                # Format the result nicely
                formatted_response = self._format_response(result)
                self._add_to_history("assistant", formatted_response)
                return formatted_response

            except Exception as e:
                error_msg = f"Error executing command: {str(e)}"
                self.logger.error(error_msg)
                return self._format_response(error_msg)

        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            self.logger.error(error_msg)
            return self._format_response(error_msg)
