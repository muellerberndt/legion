"""Autobot - A fully functional autonomous agent that can plan and execute tasks"""

from typing import Dict, Any, List, Optional
import time
import uuid
import json
from dataclasses import dataclass
from src.util.logging import Logger
from src.actions.registry import ActionRegistry
from src.ai.llm import chat_completion
from src.jobs.manager import JobManager
from src.util.command_parser import CommandParser
from src.actions.result import ActionResult, ResultType


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
        base_prompt += '/file_search "is Ownable"\n'

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

    async def execute_command(self, command: str, param_str: str) -> Any:
        """Execute a registered command"""
        # Handle empty command case for conclusion
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
                args = param_str
            else:
                args = self.command_parser.parse_arguments(param_str, spec)
            self.command_parser.validate_arguments(args, spec)

            # Execute the command
            if isinstance(args, dict):
                result = await handler(**args)
            else:
                result = await handler(*args)

            # Debug logging
            self.logger.info(f"Command result type: {type(result)}")
            if isinstance(result, ActionResult):
                self.logger.info(f"ActionResult type: {result.type}")
                if result.type == ResultType.JOB:
                    self.logger.info(f"Job ID: {result.job_id}")

                    # Wait for job completion
                    job_manager = await JobManager.get_instance()
                    try:
                        job_result = await job_manager.wait_for_job_result(result.job_id)
                        self.logger.info(f"Job completed with result: {job_result}")
                        return job_result  # Return job result directly
                    except TimeoutError:
                        raise ValueError(f"Timeout waiting for job {result.job_id} to complete")
                    except Exception as e:
                        raise ValueError(f"Error waiting for job {result.job_id}: {str(e)}")

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
                value = state[key]
                # Convert ActionResult to dict if needed
                if isinstance(value, ActionResult):
                    value = value.to_dict()
                prepared_state[key] = value

        return prepared_state

    async def plan_next_step(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """Plan the next step based on current state"""
        try:
            # Ensure we have a valid state dictionary
            if not current_state:
                current_state = {}

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
""",
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
                command_name = command_parts[0].lstrip("/")  # Strip leading slash
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

                # Execute next step with callback
                step_result = await self.execute_step(task)

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

    async def execute_step(self, task: Dict[str, Any]) -> AutobotResult:
        """Execute a single step of the task"""
        try:
            # Get next step from AI
            plan = await self.plan_next_step(task)

            # Handle direct responses (no command needed)
            if not plan["command"].strip():
                if plan["is_final"]:
                    self.record_step(
                        action="response",
                        input_data={"command": ""},
                        output_data={"result": plan["output"]},
                        reasoning=plan["thought"],
                        next_action="complete",
                    )
                    self.state["result"] = plan["output"]
                    self.state["status"] = "completed"
                    self.state["is_final"] = True
                    return AutobotResult(success=True, data={"result": plan["output"]})
                else:
                    self.record_step(
                        action="response",
                        input_data={"command": ""},
                        output_data={"result": plan["output"]},
                        reasoning=plan["thought"],
                        next_action="continue",
                    )
                    return AutobotResult(success=True, data={"result": plan["output"]})

            # Execute the command
            command_parts = plan["command"].split(maxsplit=1)
            command = command_parts[0].lstrip("/")  # Strip leading slash
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

                if plan["is_final"]:
                    self.state["result"] = plan["output"]
                    self.state["status"] = "completed"

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
