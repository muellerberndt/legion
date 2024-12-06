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
<code>/help</code>  # List all commands
<code>/help search</code>  # Show help for search command
<code>/help agent</code>  # Show help for agent command""",
        agent_hint="Use this command to learn about available commands and their usage. Without arguments it shows all commands, with an argument it shows detailed help for that command.",
        arguments=[
            ActionArgument(
                name="command",
                description="Optional command name to get detailed help for",
                required=False
            )
        ]
    )
    
    def __init__(self):
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
                    f"<b>Command:</b> {action_spec.name}",
                    f"<b>Description:</b> {action_spec.description}",
                    "",
                    action_spec.help_text,
                    "",
                    "<b>Arguments:</b>"
                ]
                
                for arg in action_spec.arguments or []:
                    req = "(required)" if arg.required else "(optional)"
                    lines.append(f"  • {arg.name}: {arg.description} {req}")
                    
                return "\n".join(lines)
                
            else:
                # List all available commands
                lines = ["<b>Available Commands:</b>"]
                
                for name, (_, spec) in sorted(self.registry.get_actions().items()):
                    lines.append(f"  • <code>/{name}</code>: {spec.description}")
                    
                lines.append("\nUse <code>/help &lt;command&gt;</code> for detailed information about a specific command.")
                return "\n".join(lines)
                
        except Exception as e:
            self.logger.error(f"Help action failed: {str(e)}")
            return f"Error getting help: {str(e)}" 