from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.actions.result import ActionResult
from src.util.logging import Logger

class HelpAction(BaseAction):
    """Show available commands and their descriptions"""
    
    spec = ActionSpec(
        name="help",
        description="Show a list of available commands and their descriptions",
        arguments=[
            ActionArgument(name="command", description="Command to get help for", required=False)
        ]
    )
    
    def __init__(self):
        super().__init__()
        self.logger = Logger("HelpAction")
        self._registry = None
        
    async def execute(self, command: str = None) -> ActionResult:
        """List all available commands or show help for a specific command"""
        # Import here to avoid circular imports
        from src.actions.registry import ActionRegistry
        
        if not self._registry:
            self._registry = ActionRegistry()
            
        actions = self._registry.get_actions()
        
        # If a command is specified, show detailed help for that command
        if command:
            if command not in actions:
                return ActionResult(
                    content=f"Command not found: {command}"
                )
                
            _, spec = actions[command]
            help_lines = [
                f"<b>Command: /{command}</b>",
                f"Description: {spec.description}",
            ]
            
            if spec.arguments:
                help_lines.append("\nArguments:")
                for arg in spec.arguments:
                    required = "(required)" if arg.required else "(optional)"
                    help_lines.append(f"- {arg.name}: {arg.description} {required}")
                    
            return ActionResult(
                content="\n".join(help_lines)
            )
        
        # Otherwise, list all commands
        help_lines = ["<b>Available Commands:</b>"]
        for name, (_, spec) in sorted(actions.items()):
            description = spec.description if hasattr(spec, 'description') else 'No description available'
            help_lines.append(f"/{name} - {description}")
            
        return ActionResult(
            content="\n".join(help_lines)
        ) 