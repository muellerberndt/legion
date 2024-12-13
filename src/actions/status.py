from src.actions.base import BaseAction, ActionSpec
from src.backend.database import DBSessionMixin
from src.models.base import Asset, Project
from sqlalchemy import select, func
from src.util.logging import Logger
from src.config.config import Config
from src.webhooks.server import WebhookServer


class StatusAction(BaseAction, DBSessionMixin):
    """Action to show system status information"""

    spec = ActionSpec(
        name="status",
        description="Show system status information",
        help_text="""Show current system status information.

Usage:
/status

Shows:
- List of active webhook handlers
- List of active extensions
- Number of projects in database
- Number of assets in database""",
        agent_hint="Use this command to check the current status of the system, including webhook handlers, extensions, and database statistics.",
        arguments=[],
    )

    def __init__(self):
        DBSessionMixin.__init__(self)
        self.logger = Logger("StatusAction")

    async def execute(self, *args, **kwargs) -> str:
        """Execute the status action"""
        try:
            # Get webhook server instance
            webhook_server = await WebhookServer.get_instance()
            active_handlers = list(webhook_server.handlers.keys())

            # Get active extensions
            config = Config()
            active_extensions = config.get("active_extensions", [])

            # Get database stats
            with self.get_session() as session:
                project_count = session.scalar(select(func.count()).select_from(Project))
                asset_count = session.scalar(select(func.count()).select_from(Asset))

            # Format output
            lines = [
                "📊 System Status\n",
                "Webhook Handlers:",
                f"  • Active: {', '.join(active_handlers) if active_handlers else 'None'}",
                "\nExtensions:",
                f"  • Active: {', '.join(active_extensions) if active_extensions else 'None'}",
                "\nDatabase:",
                f"  • Projects: {project_count:,}",
                f"  • Assets: {asset_count:,}",
            ]

            return "\n".join(lines)

        except Exception as e:
            self.logger.error(f"Failed to get system status: {str(e)}")
            return f"Error getting system status: {str(e)}"
