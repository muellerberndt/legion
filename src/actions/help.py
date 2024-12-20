from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.util.logging import Logger
from typing import Optional


class HelpAction(BaseAction):
    """Action to show help information about available commands"""

    spec = ActionSpec(
        name="help",
        description="Show help information about commands",
        help_text="""Get help information about available commands.

Usage:
/help [command]

Without arguments, shows a list of all available commands.
With a command name, shows detailed help for that command.

Examples:
/help  # List all commands
/help search  # Show help for search command
/help agent  # Show help for agent command""",
        agent_hint="Use this command to learn about available commands and their usage. Without arguments it shows all commands, with an argument it shows detailed help for that command.",
        arguments=[
            ActionArgument(name="command", description="Optional command name to get detailed help for", required=False)
        ],
    )

    def __init__(self):
        BaseAction.__init__(self)
        self.logger = Logger("HelpAction")

    async def execute(self, command: Optional[str] = None) -> str:
        """Execute the help action"""
        try:
            # Import here to avoid circular import
            from src.actions.registry import ActionRegistry

            self.registry = ActionRegistry()

            if command:
                # Show detailed help for specific command
                action_info = self.registry.get_action(command)
                if not action_info:
                    return f"Command '{command}' not found"

                action_spec = action_info[1]

                # Build detailed help text
                lines = [
                    f"Command: {action_spec.name}",
                    f"Description: {action_spec.description}",
                    "",
                    action_spec.help_text,
                    "",
                    "Arguments:",
                ]

                for arg in action_spec.arguments or []:
                    req = "(required)" if arg.required else "(optional)"
                    lines.append(f"  • {arg.name}: {arg.description} {req}")

                return "\n".join(lines)

            else:
                # List all available commands
                lines = ["Available Commands:"]

                for name, (_, spec) in sorted(self.registry.get_actions().items()):
                    self.logger.info(f"Command: {name}, Description: {spec.description}")
                    lines.append(f"  • /{name}: {spec.description}")

                lines.append("\nUse /help <command> for detailed information about a specific command.")
                return "\n".join(lines)

        except Exception as e:
            self.logger.error(f"Help action failed: {str(e)}")
            return f"Error getting help: {str(e)}"
