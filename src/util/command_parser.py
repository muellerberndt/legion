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
        # Split only on the first whitespace to preserve quotes in args
        message = message.lstrip("/")
        parts = message.split(None, 1)
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
            # Use shlex with posix=True to handle quotes properly
            parts = shlex.split(args_str, posix=True)

            # Check if any unquoted part contains =
            # We can detect this by comparing the original string with the split parts
            is_key_value = False
            start_idx = 0
            for part in parts:
                # Find this part in the original string
                while start_idx < len(args_str):
                    # Skip whitespace
                    while start_idx < len(args_str) and args_str[start_idx].isspace():
                        start_idx += 1

                    # If we find a quote, this part was quoted
                    if start_idx < len(args_str) and args_str[start_idx] in "\"'":
                        break

                    # If we find an equals sign before the part, it's a key-value pair
                    if start_idx < len(args_str) and args_str[start_idx] == "=":
                        is_key_value = True
                        break

                    # If we find the part and it contains an equals sign, it's a key-value pair
                    if start_idx < len(args_str) and args_str.startswith(part, start_idx) and "=" in part:
                        is_key_value = True
                        break

                    start_idx += 1

                if is_key_value:
                    break

            if is_key_value:
                kwargs = {}
                current_key = None
                current_value = []

                for part in parts:
                    # Only split on = if the part isn't quoted (doesn't start/end with quotes)
                    is_quoted = (part.startswith('"') and part.endswith('"')) or (part.startswith("'") and part.endswith("'"))
                    if "=" in part and not is_quoted:
                        # If we have a previous key, store it
                        if current_key:
                            kwargs[current_key] = " ".join(current_value)

                        # Start new key=value pair
                        key, value = part.split("=", 1)
                        current_key = key.strip()
                        current_value = [value.strip()] if value else []
                    elif current_key:
                        # Append to current value
                        current_value.append(part)
                    else:
                        # Handle case where first part doesn't contain =
                        continue

                # Store the last key=value pair
                if current_key:
                    kwargs[current_key] = " ".join(current_value)

                return kwargs

            # Return as positional arguments
            return parts

        except ValueError as e:
            raise ValueError(f"Failed to parse arguments: {str(e)}")

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
            # For single argument commands, join all args if needed
            if spec and len(spec.arguments) == 1:
                return True  # Already handled in parse_arguments

            required_params = [arg.name for arg in spec.arguments if arg.required]
            if required_params and len(args) < len(required_params):
                raise ValueError(f"Not enough arguments. Required: {len(required_params)}, got: {len(args)}")

            max_args = len(spec.arguments)
            if max_args > 0 and len(args) > max_args:
                raise ValueError(f"Too many arguments. Maximum: {max_args}, got: {len(args)}")

        return True
