"""Action for echoing user input - example extension"""

from src.actions.base import BaseAction, ActionSpec, ActionArgument


class EchoAction(BaseAction):
    """Action that echoes back the user's input"""

    spec = ActionSpec(
        name="echo",
        description="Echo back the provided text",
        help_text="""Usage: /echo <text>

Simply echoes back whatever text you provide. Useful for testing and as an example extension.

Example:
/echo Hello, world!""",
        agent_hint="Use this command when you want to echo back text exactly as provided by the user",
        arguments=[ActionArgument(name="text", description="The text to echo back", required=True)],
    )

    async def execute(self, *args, **kwargs) -> str:
        """Echo back the provided text"""
        if not args:
            return "Please provide some text to echo"

        return " ".join(args)
