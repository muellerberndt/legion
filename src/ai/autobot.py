"""Autobot - A fully functional autonomous agent that can plan and execute tasks"""

from typing import Dict, Any, List, Optional
import time
import uuid
import json
from dataclasses import dataclass
from src.util.logging import Logger
from src.actions.registry import ActionRegistry
from src.ai.llm import chat_completion


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

    async def execute_command(self, command: str, param_str: str) -> Any:
        """Execute a registered command"""
        # Handle empty command case for conclusion
        if not command:
            return self.get_execution_summary()

        if command not in self.commands:
            raise ValueError(f"Unknown command: {command}")

        self.logger.info(f"Executing command: {command} with params: {param_str}")

        # Get command spec
        cmd_spec = self.commands[command]
        action = self.action_registry.get_action(command)
        if not action:
            raise ValueError(f"Action not found for command: {command}")
        handler, _ = action

        # Special handling for db_query
        if command == "db_query":
            param_str = param_str.strip()
            if param_str.startswith("query="):
                param_str = param_str[6:].strip()
            if (param_str.startswith("'") and param_str.endswith("'")) or (
                param_str.startswith('"') and param_str.endswith('"')
            ):
                param_str = param_str[1:-1].strip()
            try:
                query_json = json.loads(param_str)
                if "limit" not in query_json:
                    query_json["limit"] = 10
                return await handler(json.dumps(query_json))
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid query format: {str(e)}")

        # If command takes no parameters, ignore any provided
        if not cmd_spec.required_params and not cmd_spec.optional_params:
            return await handler()

        # Clean up parameter string
        param_str = param_str.strip()
        if (param_str.startswith("'") and param_str.endswith("'")) or (param_str.startswith('"') and param_str.endswith('"')):
            param_str = param_str[1:-1].strip()

        # Parse parameters
        kwargs = {}
        if "=" in param_str:
            # Handle key=value parameters
            param_pairs = param_str.split()
            for pair in param_pairs:
                if "=" not in pair:
                    continue
                param_name, param_value = pair.split("=", 1)
                param_name = param_name.strip()
                param_value = param_value.strip()
                if (param_value.startswith("'") and param_value.endswith("'")) or (
                    param_value.startswith('"') and param_value.endswith('"')
                ):
                    param_value = param_value[1:-1]
                kwargs[param_name] = param_value
            return await handler(**kwargs)
        else:
            # Handle positional parameters
            if not param_str:
                args = []
            elif cmd_spec.positional_params:
                # If command defines positional parameters, use them
                args = [param_str]
            else:
                # Split on whitespace for multiple positional parameters
                args = param_str.split()
            return await handler(*args)

    async def plan_next_step(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """Plan the next step based on current state"""
        try:
            # Prepare context for the LLM
            messages = [
                {"role": "system", "content": self.system_prompt},
                {
                    "role": "system",
                    "content": """Plan the next step based on the current state and available commands.
Your response must be a JSON object with these fields:
{
    "reasoning": "Your thought process for choosing this step",
    "action": "command_name (no preceding slash)",
    "parameters": "parameter string for the command",
    "is_final": boolean (true if this should be the last step)
}
Do not enter loops and aim to complete the task in the least number of steps.""",
                },
                {"role": "user", "content": f"Current state: {json.dumps(current_state, indent=2)}"},
            ]

            # Get plan from LLM
            response = await chat_completion(messages)

            self.logger.info(f"Agent response: {response}")

            try:
                # Strip markdown code block syntax if present
                json_str = response
                if "```json" in json_str:
                    json_str = json_str.split("```json", 1)[1]
                if "```" in json_str:
                    json_str = json_str.split("```", 1)[0]
                json_str = json_str.strip()

                plan = json.loads(json_str)
                required_fields = ["reasoning", "action", "parameters", "is_final"]
                if not all(field in plan for field in required_fields):
                    raise ValueError(f"Missing required fields in plan. Got: {list(plan.keys())}")
                return plan
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON in plan: {response}")

        except Exception as e:
            self.logger.error(f"Error in planning: {str(e)}")
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

    async def execute_step(self) -> AutobotResult:
        """Execute a single step of the task"""
        try:
            # Plan next step
            plan = await self.plan_next_step(self.state)

            # Execute the planned action
            command = plan["action"]
            parameters = plan["parameters"]

            try:
                # If concluding with empty action, return summary
                if not command and plan["is_final"]:
                    summary = self.get_execution_summary()
                    self.state["result"] = summary
                    self.state["status"] = "completed"
                    return AutobotResult(success=True, data={"result": summary})

                result = await self.execute_command(command, parameters)

                # Record the step
                self.record_step(
                    action=command,
                    input_data={"parameters": parameters},
                    output_data={"result": result},
                    reasoning=plan["reasoning"],
                    next_action="complete" if plan["is_final"] else "continue",
                )

                # Update state
                self.state["last_result"] = result
                self.state["is_final"] = plan["is_final"]
                if plan["is_final"]:
                    # For final steps, include both the result and a summary
                    summary = self.get_execution_summary()
                    self.state["result"] = {"final_result": result, "execution_summary": summary}
                    self.state["status"] = "completed"
                elif self.step_count >= 3:  # Add a step limit for simple queries
                    summary = self.get_execution_summary()
                    self.state["result"] = {
                        "final_result": result,
                        "execution_summary": summary,
                        "note": "Task completed after maximum steps",
                    }
                    self.state["status"] = "completed"
                    self.state["is_final"] = True
                    return AutobotResult(success=True, data={"result": self.state["result"]})

                return AutobotResult(success=True, data={"result": result})

            except Exception as e:
                self.logger.error(f"Error executing command: {str(e)}")
                return AutobotResult(success=False, error=str(e))

        except Exception as e:
            self.logger.error(f"Error in step execution: {str(e)}")
            return AutobotResult(success=False, error=str(e))

    async def execute_task(self, task: Dict[str, Any]) -> AutobotResult:
        """Execute a task with safety limits and state tracking"""
        self.start_time = time.time()
        self.step_count = 0
        self.state = {"task": task, "status": "started"}
        self.execution_id = str(uuid.uuid4())
        self.execution_steps = []

        try:
            while self.step_count < self.max_steps:
                # Check timeout
                if time.time() - self.start_time > self.timeout:
                    self.state["status"] = "failed"
                    self.state["error"] = f"Task timed out after {self.timeout} seconds"
                    return AutobotResult(success=False, error=f"Task timed out after {self.timeout} seconds")

                # Execute next step
                self.step_count += 1
                step_result = await self.execute_step()

                # Handle step result
                if not step_result.success:
                    self.state["status"] = "failed"
                    self.state["error"] = step_result.error
                    return step_result

                if step_result.requires_user_input:
                    self.state["status"] = "waiting_for_input"
                    return step_result

                if self.is_task_complete():
                    result = AutobotResult(
                        success=True, data={"result": self.state.get("result"), "steps_taken": self.step_count}
                    )
                    self.state["status"] = "completed"
                    return result

            # Max steps reached
            self.state["status"] = "failed"
            self.state["error"] = f"Task exceeded maximum steps ({self.max_steps})"
            return AutobotResult(success=False, error=f"Task exceeded maximum steps ({self.max_steps})")

        except Exception as e:
            self.logger.error(f"Error in task execution: {str(e)}")
            self.state["status"] = "failed"
            self.state["error"] = str(e)
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
