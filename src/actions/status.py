from src.actions.base import BaseAction, ActionSpec
from src.watchers.manager import WatcherManager
from src.watchers.registry import WatcherRegistry
from src.backend.database import DBSessionMixin
from src.models.base import Asset, Project
from sqlalchemy import select, func
from src.util.logging import Logger
from src.config.config import Config


class StatusAction(BaseAction, DBSessionMixin):
    """Action to show system status information"""

    spec = ActionSpec(
        name="status",
        description="Show system status information",
        help_text="""Show current system status information.

Usage:
/status

Shows:
- Number of active jobs
- List of registered watchers
- List of currently running watchers
- List of active extensions
- Number of projects in database
- Number of assets in database""",
        agent_hint="Use this command to check the current status of the system, including active jobs, watchers, extensions, and database statistics.",
        arguments=[],
    )

    def __init__(self):
        DBSessionMixin.__init__(self)
        self.logger = Logger("StatusAction")

    async def execute(self, *args, **kwargs) -> str:
        """Execute the status action"""
        try:
            # Get watcher info
            watcher_registry = WatcherRegistry()
            watcher_registry.initialize()

            # Get registered watchers
            registered_watchers = list(watcher_registry.watchers.keys())

            # Get currently running watchers from WatcherManager singleton
            watcher_manager = WatcherManager.get_instance()
            running_watchers = []

            self.logger.info(f"Watcher manager: {watcher_manager.watchers}")
            self.logger.info(f"Registered watchers: {registered_watchers}")
            for name, watcher in watcher_manager.watchers.items():
                # A watcher is running if its _watch_task exists and is not done
                if hasattr(watcher, "_watch_task") and watcher._watch_task and not watcher._watch_task.done():
                    running_watchers.append(name)
                    self.logger.info(f"Watcher {name} is running with task {watcher._watch_task}")
                else:
                    self.logger.info(f"Watcher {name} is not running: task={getattr(watcher, '_watch_task', None)}")

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
                "Watchers:",
                f"  • Registered: {', '.join(registered_watchers)}",
                f"  • Running: {', '.join(running_watchers) if running_watchers else 'None'}",
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
