"""Base class for AI agents with shared functionality"""

from typing import Any, Optional, Tuple
import json
from src.util.logging import Logger
from src.actions.registry import ActionRegistry
from src.jobs.manager import JobManager


class BaseAgent:
    """Base class for AI agents with shared functionality"""

    def __init__(self, action_registry: Optional[ActionRegistry] = None):
        """Initialize the base agent"""
        self.logger = Logger(self.__class__.__name__)
        self.action_registry = action_registry or ActionRegistry()
        if not action_registry:
            self.action_registry.initialize()

        # Get all available commands
        self.commands = self.action_registry._get_agent_command_instructions()
        self.logger.info("Initialized with commands:", extra_data={"commands": list(self.commands.keys())})

    def _truncate_result(self, result: Any, max_length: int = 4000) -> Any:
        """Truncate a result to a reasonable size to avoid LLM context limits"""
        # Try to parse JSON string if the input is a string
        if isinstance(result, str):
            try:
                data = json.loads(result)
                # After parsing, handle as Python object
                truncated = self._truncate_result(data, max_length)
                return json.dumps(truncated)
            except json.JSONDecodeError:
                # Handle non-JSON strings
                if len(result) <= max_length:
                    return result
                return result[: max_length - 15] + "... (truncated)"

        # Handle lists
        if isinstance(result, list):
            original_count = len(result)
            if original_count > 10:
                return {"results": result[:10], "note": f"Results truncated to 10 of {original_count} total items"}
            return result

        # Handle dictionaries
        if isinstance(result, dict):
            # First truncate any results array if present
            if "results" in result and isinstance(result["results"], list):
                original_count = len(result["results"])
                if original_count > 10:
                    truncated = result.copy()
                    truncated["results"] = result["results"][:10]
                    truncated["note"] = f"Results truncated to 10 of {original_count} total matches"
                    return truncated

            # For other dictionaries, recursively truncate all string values
            truncated = {}
            for key, value in result.items():
                if isinstance(value, (dict, list)):
                    truncated[key] = self._truncate_result(value, max_length)
                elif isinstance(value, str):
                    truncated[key] = self._truncate_result(value, max_length)
                else:
                    truncated[key] = value
            return truncated

        # Handle other types
        return str(result)

    async def execute_command(self, command: str, param_str: str) -> Any:
        """Execute a command with the given parameters"""
        args, kwargs = self._parse_parameters(command, param_str)

        # Get the action handler
        handler, _ = self.action_registry.get_action(command)
        if not handler:
            raise ValueError(f"Unknown command: {command}")

        # Execute the action
        result = await handler(*args, **kwargs)

        # Handle job results
        if isinstance(result, str) and result.startswith("Job started with ID:"):
            job_id = result.split(":")[-1].strip()
            job_manager = await JobManager.get_instance()
            job_result = await job_manager.get_job_result(job_id)

            if not job_result.get("success", False):
                raise ValueError(job_result.get("error", "Job failed"))

            # Truncate the job result data if needed
            if "data" in job_result:
                job_result["data"] = self._truncate_result(job_result["data"])
            return job_result

        # Truncate result if needed
        return self._truncate_result(result)

    def _parse_parameters(self, command: str, param_str: str) -> Tuple[list, dict]:
        """Parse command parameters into args and kwargs"""
        # Clean up parameter string
        param_str = param_str.strip()
        if (param_str.startswith("'") and param_str.endswith("'")) or (param_str.startswith('"') and param_str.endswith('"')):
            param_str = param_str[1:-1].strip()

        # Get command spec
        cmd_spec = self.commands.get(command)
        if not cmd_spec:
            raise ValueError(f"Unknown command: {command}")

        # If command takes no parameters, return empty args and kwargs
        if not cmd_spec.arguments:
            return [], {}

        # Parse parameters
        if "=" in param_str:
            # Handle key=value parameters
            kwargs = {}
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
            return [], kwargs
        else:
            # Handle positional parameters
            if not param_str:
                return [], {}

            # Get first required parameter as positional if agent_hint suggests it
            positional_param = None
            if cmd_spec.agent_hint and any(
                hint in cmd_spec.agent_hint.lower() for hint in ["first argument", "first parameter"]
            ):
                required_params = [arg.name for arg in cmd_spec.arguments if arg.required]
                if required_params:
                    positional_param = required_params[0]

            if positional_param:
                # If command defines positional parameters, use them
                return [param_str], {}
            else:
                # Split on whitespace for multiple positional parameters
                return param_str.split(), {}
