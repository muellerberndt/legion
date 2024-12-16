"""Command parsing utilities"""

import shlex
from typing import Dict, List, Tuple, Union, Optional
from src.actions.base import ActionSpec


class CommandParser:
    """Unified command parser for all interfaces"""

    @staticmethod
    def parse_command(message: str) -> Tuple[str, str]:
        """Parse a command message into command name and raw argument string.

        Args:
            message: The full command message (e.g. "/search pattern=test")

        Returns:
            Tuple of (command_name, raw_args_string)
        """
        parts = message.lstrip("/").split(None, 1)
        command = parts[0] if parts else ""
        args_str = parts[1] if len(parts) > 1 else ""
        return command, args_str

    @staticmethod
    def parse_arguments(args_str: str, spec: Optional[ActionSpec] = None) -> Union[List[str], Dict[str, str]]:
        """Parse command arguments based on the command spec.

        Args:
            args_str: The raw argument string
            spec: Optional command specification

        Returns:
            Either a list of positional arguments or a dict of keyword arguments
        """
        if not args_str:
            return []

        try:
            # Use shlex to handle all quoting and escaping
            parts = shlex.split(args_str)

            # If any part contains '=', treat as key=value pairs
            if any("=" in part for part in parts):
                kwargs = {}
                for part in parts:
                    if "=" not in part:
                        continue
                    key, value = part.split("=", 1)
                    kwargs[key.strip()] = value.strip()
                return kwargs

            # Otherwise return as positional arguments
            return parts

        except ValueError:
            # If shlex fails, return as single argument
            return [args_str.strip()]

    @staticmethod
    def validate_arguments(args: Union[List[str], Dict[str, str]], spec: Optional[ActionSpec] = None) -> bool:
        """Validate arguments against command spec.

        Args:
            args: Parsed arguments (list or dict)
            spec: Optional command specification

        Returns:
            True if arguments are valid, False otherwise

        Raises:
            ValueError: If arguments are invalid with explanation
        """
        # If no spec provided, any arguments are valid
        if spec is None or not spec.arguments:
            return True

        if isinstance(args, dict):
            # Get required and optional parameters from spec arguments
            required_params = [arg.name for arg in spec.arguments if arg.required]
            valid_params = {arg.name for arg in spec.arguments}

            # Check required parameters
            missing = [p for p in required_params if p not in args]
            if missing:
                raise ValueError(f"Missing required parameters: {', '.join(missing)}")

            # Check for unknown parameters
            if valid_params:  # Only check for unknown params if spec defines valid ones
                unknown = [p for p in args if p not in valid_params]
                if unknown:
                    raise ValueError(f"Unknown parameters: {', '.join(unknown)}")

        else:  # List of positional arguments
            required_params = [arg.name for arg in spec.arguments if arg.required]
            if required_params and len(args) < len(required_params):
                raise ValueError(f"Not enough arguments. Required: {len(required_params)}, got: {len(args)}")

            max_args = len(spec.arguments)
            if max_args > 0 and len(args) > max_args:
                raise ValueError(f"Too many arguments. Maximum: {max_args}, got: {len(args)}")

        return True
