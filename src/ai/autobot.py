"""Autobot - A fully functional autonomous agent that can plan and execute tasks"""

from typing import Dict, Any, List, Optional
import time
import uuid
import json
from dataclasses import dataclass
from src.util.logging import Logger
from src.actions.registry import ActionRegistry
from src.ai.llm import chat_completion
import re
from src.jobs.manager import JobManager
from src.util.command_parser import CommandParser


@dataclass
class ExecutionStep:
    """Record of a single execution step"""

    step_number: int
    action: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    reasoning: str
    next_action: str
    timestamp: float = time.time()


@dataclass
class AutobotResult:
    """Result of an Autobot operation"""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    requires_user_input: bool = False
    user_prompt: Optional[str] = None


class Autobot:
    """A fully functional autonomous agent that can plan and execute tasks"""

    def __init__(
        self,
        action_registry: Optional[ActionRegistry] = None,
        custom_prompt: Optional[str] = None,
        command_names: Optional[List[str]] = None,
    ):
        self.logger = Logger(self.__class__.__name__)

        # Use provided action registry or create a new one
        self.action_registry = action_registry or ActionRegistry()
        if not action_registry:
            self.action_registry.initialize()

        # Get available commands from action registry
        self.commands = self.action_registry._get_agent_command_instructions()
        if command_names:
            # Filter commands if specific ones are requested
            self.commands = {name: cmd for name, cmd in self.commands.items() if name in command_names}

        # Initialize command parser
        self.command_parser = CommandParser()

        # Build system prompt
        self.system_prompt = self._build_system_prompt(custom_prompt)

        # Initialize execution state
        self.max_steps = 10
        self.timeout = 300
        self.step_count = 0
        self.start_time: Optional[float] = None
        self.state: Dict[str, Any] = {}
        self.execution_id: Optional[str] = None
        self.execution_steps: List[ExecutionStep] = []

        self.logger.info(
            "Initialized Autobot",
            extra_data={
                "command_count": len(self.commands),
                "commands": list(self.commands.keys()),
            },
        )

    def _build_system_prompt(self, custom_prompt: Optional[str] = None) -> str:
        """Build the complete system prompt including available commands"""
        base_prompt = custom_prompt or "You are an autonomous AI agent capable of planning and executing tasks."
        base_prompt += "\n\nYour capabilities:\n"
        base_prompt += "1. You can break down complex tasks into smaller steps\n"
        base_prompt += "2. You can plan and execute each step using available commands\n"
        base_prompt += "3. You can adapt your plan based on the results of each step\n"
        base_prompt += "4. You maintain state and can track progress across multiple steps\n\n"
        base_prompt += (
            "IMPORTANT: When a command returns a result, you should analyze it and decide if the task is complete.\n"
        )
        base_prompt += "Set is_final=true when:\n"
        base_prompt += "1. You have the information needed to answer the user's question\n"
        base_prompt += "2. The command result indicates success or completion\n"
        base_prompt += "3. The command result shows an error or failure\n"
        base_prompt += "4. You've gathered enough information to provide a meaningful response\n\n"
        base_prompt += "CRITICAL INSTRUCTIONS:\n"
        base_prompt += "1. Don't truncate your output. Always show complete results.\n"
        base_prompt += "3. ALWAYS quote arguments that contain spaces or special characters, e.g.:\n"
        base_prompt += "db_query '{'from': 'projects', 'order_by': [{'field': 'id', 'direction': 'desc'}], 'limit': 10}'\n"

        if self.commands:
            base_prompt += "Available commands:\n\n"
            for name, cmd in self.commands.items():
                base_prompt += f"/{name}\n"
                base_prompt += f"Description: {cmd.description}\n"
                if cmd.help_text:
                    base_prompt += f"Help: {cmd.help_text}\n"
                if cmd.agent_hint:
                    base_prompt += f"Usage hint: {cmd.agent_hint}\n"
                base_prompt += "\n"

        return base_prompt

    async def _wait_for_job(self, job_id: str, timeout: int = 300) -> Dict[str, Any]:
        """Wait for a job to complete and return its result."""
        job_manager = await JobManager.get_instance()
        return await job_manager.wait_for_job_result(job_id, timeout)

    def _extract_job_id(self, result: str) -> Optional[str]:
        """Extract job ID from a command result if present.

        Looks for patterns like:
        - "Started job with ID: abc-123"
        - "Job ID: abc-123"
        - "job abc-123"

        Args:
            result: The command result string

        Returns:
            The job ID if found, None otherwise
        """
        # Common patterns for job IDs
        patterns = [
            r"[Jj]ob (?:ID: )?([a-f0-9-]+)",
            r"[Jj]ob_id: ([a-f0-9-]+)",
            r"[Ss]tarted.*[Jj]ob.*?([a-f0-9-]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, result)
            if match:
                return match.group(1)
        return None

    async def execute_command(self, command: str, param_str: str) -> Any:
        """Execute a registered command"""
        # Handle empty command case for conclusion

        # Remove preceding slash
        command = command.lstrip("/")

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
                # Otherwise parse the string into arguments
                args = self.command_parser.parse_arguments(param_str, spec)
            self.command_parser.validate_arguments(args, spec)

            # Execute the command
            if isinstance(args, dict):
                result = await handler(**args)
            else:
                result = await handler(*args)

            # Check for job ID in result
            if isinstance(result, str):
                job_id = self._extract_job_id(result)
                if job_id:
                    self.logger.info(f"Detected job ID {job_id}, waiting for completion...")
                    try:
                        job_result = await self._wait_for_job(job_id)
                        if not job_result["success"]:
                            if "error" in job_result:
                                raise ValueError(job_result["error"])
                            raise ValueError("Job failed without specific error message")
                        return job_result
                    except (TimeoutError, ValueError) as e:
                        self.logger.error(f"Error waiting for job: {str(e)}")
                        raise

            return result

        except Exception as e:
            self.logger.error(f"Error executing command: {str(e)}")
            raise

    def _truncate_state_for_llm(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare state for LLM without truncating results"""
        # Create a copy of the state to avoid modifying the original
        prepared_state = {}

        # Always include task and status
        if "task" in state:
            prepared_state["task"] = state["task"]
        if "status" in state:
            prepared_state["status"] = state["status"]

        # Include last result and other important fields without truncation
        for key in ["last_result", "error", "result"]:
            if key in state:
                prepared_state[key] = state[key]

        return prepared_state

    async def plan_next_step(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """Plan the next step based on current state"""
        try:
            # Truncate state before sending to LLM
            truncated_state = self._truncate_state_for_llm(current_state)

            # For complex queries requiring commands, proceed with normal planning
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
1. NEVER truncate your output. Show ALL results completely.
2. Do not add notes like "(truncated)" or "for brevity".
3. When formatting lists or results, include ALL items with their complete information.

Example responses:

{
    "thought": "I need to get the list of projects from the database",
    "command": "db_query '{\"from\": \"projects\", \"limit\": 5}'",
    "output": "",
    "is_final": false
}

{
    "thought": "I have the project data, now I'll format it nicely for the user",
    "command": "",
    "output": "Here are the projects:\n• Project A - Complete description of project A with all details\n• Project B - Complete description of project B with all details",
    "is_final": true
}

IMPORTANT:
1. Return ONLY the JSON object, no other text
2. Use double quotes for strings
3. Use true/false (lowercase) for booleans
4. If using a command, it must be one of the available commands
5. Arguments containing spaces must be quoted
6. NEVER truncate or omit information from results

Available commands and their parameters:"""
                    + "\n"
                    + "\n".join(
                        f"- {name}: {cmd.description}\n  Parameters: {', '.join(arg.name + ('*' if arg.required else '') for arg in cmd.arguments)}"
                        for name, cmd in self.commands.items()
                    )
                    + "\n",
                },
                {"role": "user", "content": f"Current state: {json.dumps(truncated_state, indent=2)}"},
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

    def record_step(self, action: str, input_data: Dict, output_data: Dict, reasoning: str, next_action: str) -> None:
        """Record a step in memory"""
        step = ExecutionStep(
            step_number=self.step_count,
            action=action,
            input_data=input_data,
            output_data=output_data,
            reasoning=reasoning,
            next_action=next_action,
        )
        self.execution_steps.append(step)

    def is_task_complete(self) -> bool:
        """Check if the task is complete based on state"""
        return self.state.get("status") == "completed" or self.state.get("is_final", False) or "result" in self.state

    async def execute_task(self, task: Dict[str, Any]) -> AutobotResult:
        """Execute a task with safety limits and state tracking"""
        self.start_time = time.time()
        self.step_count = 0
        self.state = {"task": task, "status": "started"}
        self.execution_id = str(uuid.uuid4())
        self.execution_steps = []

        try:
            while True:
                # Check timeout
                if time.time() - self.start_time > self.timeout:
                    self.state["status"] = "failed"
                    error_msg = f"Task timed out after {self.timeout} seconds"
                    self.state["error"] = error_msg
                    return AutobotResult(success=False, error=error_msg)

                # Execute next step
                step_result = await self.execute_step()

                # Increment step count and check limit
                self.step_count += 1
                if self.step_count >= self.max_steps and not self.is_task_complete():
                    self.state["status"] = "failed"
                    error_msg = f"Task exceeded maximum steps ({self.max_steps})"
                    self.state["error"] = error_msg
                    return AutobotResult(success=False, error=error_msg)

                # Handle step result
                if not step_result.success:
                    self.state["status"] = "failed"
                    self.state["error"] = step_result.error
                    return step_result

                if step_result.requires_user_input:
                    self.state["status"] = "waiting_for_input"
                    return step_result

                if self.is_task_complete():
                    # Get the final result from the last step
                    final_result = None
                    if step_result.data:
                        if isinstance(step_result.data, dict):
                            if "result" in step_result.data:
                                final_result = step_result.data["result"]
                            elif "final_result" in step_result.data:
                                final_result = step_result.data["final_result"]
                        else:
                            final_result = step_result.data

                    # If we have a final result from the last step, use it
                    if final_result:
                        self.state["result"] = final_result
                    # Otherwise, generate a response based on the task and results
                    else:
                        # Get the last command result
                        last_result = self.state.get("last_result")

                        # Format a response based on the results
                        if isinstance(last_result, dict) and "data" in last_result:
                            self.state["result"] = last_result["data"]
                        elif isinstance(last_result, (str, list, dict)):
                            self.state["result"] = last_result
                        else:
                            self.state["result"] = "Task completed successfully"

                    self.state["status"] = "completed"
                    return AutobotResult(success=True, data={"result": self.state["result"], "steps_taken": self.step_count})

        except Exception as e:
            self.logger.error(f"Error in task execution: {str(e)}")
            self.state["status"] = "failed"
            self.state["error"] = str(e)
            return AutobotResult(success=False, error=str(e))

    async def execute_step(self) -> AutobotResult:
        """Execute a single step of the task"""
        try:
            # Plan next step
            plan = await self.plan_next_step(self.state)

            # Handle empty command (direct response)
            if not plan["command"].strip():
                # For final steps, the reasoning should be the formatted result
                if plan["is_final"]:
                    # Record the step
                    self.record_step(
                        action="response",
                        input_data={"command": ""},
                        output_data={"result": plan["output"]},
                        reasoning=plan["thought"],
                        next_action="complete",
                    )

                    # Update state with the formatted result
                    self.state["result"] = plan["output"]
                    self.state["status"] = "completed"
                    self.state["is_final"] = True
                    return AutobotResult(success=True, data={"result": plan["output"]})
                else:
                    # For non-final direct responses
                    self.record_step(
                        action="response",
                        input_data={"command": ""},
                        output_data={"result": plan["output"]},
                        reasoning=plan["thought"],
                        next_action="continue",
                    )
                    return AutobotResult(success=True, data={"result": plan["output"]})

            # Split command into name and parameters
            command_parts = plan["command"].split(maxsplit=1)
            command = command_parts[0]
            param_str = command_parts[1] if len(command_parts) > 1 else ""

            try:
                # Execute the command
                result = await self.execute_command(command, param_str)

                self.logger.info(f"Command result: {result}")

                # Record the step
                self.record_step(
                    action=command,
                    input_data={"command": plan["command"]},
                    output_data={"result": result},
                    reasoning=plan["thought"],
                    next_action="complete" if plan["is_final"] else "continue",
                )

                # Update state
                self.state["last_result"] = result
                self.state["is_final"] = plan["is_final"]

                # For final steps after a command, use the reasoning as the formatted result
                if plan["is_final"]:
                    self.state["result"] = plan["output"]
                    self.state["status"] = "completed"

                # Return the result
                return AutobotResult(success=True, data={"result": plan["output"] if plan["is_final"] else result})

            except Exception as e:
                self.logger.error(f"Error executing command: {str(e)}")
                return AutobotResult(success=False, error=str(e))

        except Exception as e:
            self.logger.error(f"Error in step execution: {str(e)}")
            return AutobotResult(success=False, error=str(e))

    def get_execution_summary(self) -> Dict[str, Any]:
        """Get a summary of the execution"""
        return {
            "execution_id": self.execution_id,
            "status": self.state.get("status"),
            "steps_taken": self.step_count,
            "error": self.state.get("error"),
            "result": self.state.get("result"),
            "steps": [
                {
                    "step_number": step.step_number,
                    "action": step.action,
                    "reasoning": step.reasoning,
                    "next_action": step.next_action,
                    "timestamp": step.timestamp,
                }
                for step in self.execution_steps
            ],
        }
