"""Chatbot implementation using the new chat_completion function"""

from typing import Dict, List, Any
import json
from src.config.config import Config
from src.util.logging import Logger
from src.actions.registry import ActionRegistry
from src.ai.llm import chat_completion
from src.util.command_parser import CommandParser
import re
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

    def _format_as_html(self, content: str) -> str:
        """Format content as HTML with nice styling"""
        html = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                pre { background: #f5f5f5; padding: 10px; border-radius: 5px; }
                table { border-collapse: collapse; width: 100%; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f5f5f5; }
                .tree-view { font-family: monospace; }
                .tree-view .node { margin-left: 20px; }
                .json { color: #333; }
                .json .key { color: #0066cc; }
                .json .string { color: #008800; }
                .json .number { color: #aa0000; }
                .json .boolean { color: #aa0000; }
            </style>
        </head>
        <body>
        """

        # Try to detect and format different types of content
        if content.strip().startswith(("{", "[")):
            try:
                # Format JSON with syntax highlighting
                data = json.loads(content)
                formatted = json.dumps(data, indent=2)
                html += "<pre class='json'>"
                # Add basic syntax highlighting
                formatted = formatted.replace('"', "&quot;")
                formatted = re.sub(r'(".*?"):', r'<span class="key">\1</span>:', formatted)
                formatted = re.sub(r': "(.+?)"', r': <span class="string">&quot;\1&quot;</span>', formatted)
                formatted = re.sub(r": (\d+)", r': <span class="number">\1</span>', formatted)
                formatted = re.sub(r": (true|false)", r': <span class="boolean">\1</span>', formatted)
                html += formatted
                html += "</pre>"
            except json.JSONDecodeError:
                html += f"<pre>{content}</pre>"
        elif "\n" in content and "|" in content:
            # Looks like a table, convert to HTML table
            rows = [row.strip().split("|") for row in content.strip().split("\n")]
            html += "<table>"
            for i, row in enumerate(rows):
                html += "<tr>"
                tag = "th" if i == 0 else "td"
                for cell in row:
                    html += f"<{tag}>{cell.strip()}</{tag}>"
                html += "</tr>"
            html += "</table>"
        elif content.startswith(("├", "└", "│")):
            # Looks like a tree structure
            html += "<pre class='tree-view'>"
            html += content
            html += "</pre>"
        else:
            # Default to pre-formatted text
            html += f"<pre>{content}</pre>"

        html += "</body></html>"
        return html

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
            # For complex queries requiring commands, proceed with planning
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

The "output" field will be shown directly to the user, so it should be properly formatted.
For intermediate steps (is_final=false), you can leave "output" empty.

CRITICAL INSTRUCTIONS:
1. For complex tasks that require multiple steps or jobs, use the /autobot command to delegate the task.
2. NEVER truncate your output. Show ALL results completely.
3. Do not add notes like "(truncated)" or "for brevity".
4. When formatting lists or results, include ALL items with their complete information.
5. Try to be efficient, e.g. attempt to use as few database queries as possible.

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
        """Process a message and return a response"""
        try:
            # Record user message
            self._add_to_history("user", message)

            # Initialize state for this message
            state = {"message": message, "last_result": None, "status": "started", "is_final": False}

            # Handle commands
            if message.startswith("/"):
                command, args_str = self.command_parser.parse_command(message)
                if command in self.commands:
                    try:
                        # Execute the command
                        result = await self.execute_command(command, args_str, update_callback=update_callback)

                        # Format the result based on type
                        if isinstance(result, dict):
                            # For dictionary results, extract relevant data
                            if "data" in result:
                                formatted_result = str(result["data"])
                            elif "message" in result:
                                formatted_result = str(result["message"])
                            else:
                                formatted_result = str(result)
                        else:
                            formatted_result = str(result)

                        # Add to history and return
                        self._add_to_history("assistant", formatted_result)
                        return self._format_response(formatted_result)

                    except Exception as e:
                        error_msg = f"Error executing command: {str(e)}"
                        self.logger.error(error_msg)
                        return error_msg
                else:
                    return f"Unknown command: {command}"

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
                        # Add to history and return without showing thinking process
                        self._add_to_history("assistant", plan["output"])
                        return self._format_response(plan["output"])
                    else:
                        # For non-final direct responses, continue to next step
                        state["last_result"] = plan["output"]
                        step_count += 1
                        continue

                # For command execution, show step info
                if update_callback and plan["command"].strip():
                    # Extract command name and parameters first
                    cmd_parts = plan["command"].split(maxsplit=1)
                    cmd_name = cmd_parts[0]

                    # Only show thinking process for actual commands (not direct responses)
                    if cmd_name in self.commands:
                        step_info = []
                        if plan["thought"]:
                            # Remove any special characters from thought
                            thought = plan["thought"].replace("`", "").replace("'", "").replace('"', "")
                            step_info.append(f"🤔 Thinking: {thought}")

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

                        # Initialize _last_command_msg if not exists
                        if not hasattr(self, "_last_command_msg"):
                            self._last_command_msg = None

                        # Only show command if it's different from the last one
                        command_msg = f"🛠️ Running: {cmd_name} {cmd_params}"
                        if self._last_command_msg != command_msg:
                            step_info.append(command_msg)
                            self._last_command_msg = command_msg

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
                        formatted_result = plan["output"] if plan["output"] else result
                        state["result"] = formatted_result
                        state["status"] = "completed"
                        self._add_to_history("assistant", formatted_result)
                        return self._format_response(formatted_result)

                    # For non-final steps, only return immediately if:
                    # 1. We have a result AND
                    # 2. No output is planned AND
                    # 3. No further commands are needed (based on the plan's thought)
                    if (
                        result
                        and not plan["output"]
                        and not any(cmd in plan["thought"].lower() for cmd in ["next", "then", "after", "chain", "follow"])
                    ):
                        formatted_result = self._format_response(result)
                        self._add_to_history("assistant", formatted_result)
                        return formatted_result

                    # Continue to next step
                    step_count += 1

                except Exception as e:
                    error_msg = f"Error executing command: {str(e)}"
                    self.logger.error(error_msg)
                    return self._format_response(error_msg)

        except Exception as e:
            self.logger.error(f"Error processing message: {str(e)}")
            return self._format_response(f"Error processing message: {str(e)}")
