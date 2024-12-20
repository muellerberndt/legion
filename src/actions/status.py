from src.actions.base import BaseAction, ActionSpec
from src.jobs.manager import JobManager
from src.jobs.scheduler import Scheduler
from src.webhooks.server import WebhookServer
from src.util.logging import Logger
from src.actions.result import ActionResult
from src.jobs.base import JobStatus
from src.config.config import Config
import os


class StatusAction(BaseAction):
    """Action to show system status"""

    spec = ActionSpec(
        name="status",
        description="Show system status",
        help_text="""Show the current status of the system, including:
- Job statistics
- Installed extensions
- Scheduled actions
- Webhook server status""",
        agent_hint="Use this command to check the system status",
        arguments=[],
    )

    def __init__(self):
        self.logger = Logger("StatusAction")
        self.config = Config()

    async def execute(self, *args) -> ActionResult:
        """Execute the status action"""
        try:
            lines = []

            # Add job statistics section
            lines.append("📊 Job Statistics:")
            try:
                job_manager = await JobManager.get_instance()
                jobs = await job_manager.list_jobs()

                # Count jobs by status
                running = sum(1 for job in jobs if job["status"] == JobStatus.RUNNING.value)
                completed = sum(1 for job in jobs if job["status"] == JobStatus.COMPLETED.value)
                cancelled = sum(1 for job in jobs if job["status"] == JobStatus.CANCELLED.value)

                lines.append(f"• Running: {running}")
                lines.append(f"• Completed: {completed}")
                lines.append(f"• Cancelled: {cancelled}")
            except Exception as e:
                lines.append(f"• Error getting job statistics: {str(e)}")

            # Add installed extensions section
            lines.append("\n🧩 Installed Extensions:")
            try:
                extensions_dir = self.config.get("extensions_dir", "./extensions")
                if os.path.exists(extensions_dir):
                    # Get list of directories in extensions folder
                    extension_dirs = [
                        d
                        for d in os.listdir(extensions_dir)
                        if os.path.isdir(os.path.join(extensions_dir, d)) and not d.startswith("_")
                    ]
                    if extension_dirs:
                        for ext_dir in sorted(extension_dirs):
                            lines.append(f"• {ext_dir}")
                    else:
                        lines.append("• No extensions installed")
                else:
                    lines.append("• Extensions directory not found")
            except Exception as e:
                lines.append(f"• Error getting extensions: {str(e)}")

            # Add scheduled actions section
            try:
                scheduler = await Scheduler.get_instance()
                actions = scheduler.list_actions()

                lines.append("\n📅 Scheduled Actions:")
                if actions:
                    for name, status in actions.items():
                        enabled = "✅" if status["enabled"] else "❌"
                        interval = f"{status['interval_minutes']} minutes"
                        last_run = status["last_run"] or "Never"
                        lines.append(f"{enabled} {name}")
                        lines.append(f"   • Command: {status['command']}")
                        lines.append(f"   • Interval: {interval}")
                        lines.append(f"   • Last run: {last_run}")
                        if status["next_run"]:
                            lines.append(f"   • Next run: {status['next_run']}")
                else:
                    lines.append("• No scheduled actions configured")
            except Exception as e:
                lines.append(f"• Error getting scheduled actions: {str(e)}")

            # Add webhook server status section
            try:
                webhook_server = await WebhookServer.get_instance()
                lines.append("\n🌐 Webhook Server:")
                if webhook_server and webhook_server.runner:
                    lines.append(f"• Running on port {webhook_server.port}")
                else:
                    lines.append("• Not running")
            except Exception as e:
                lines.append(f"• Error getting webhook status: {str(e)}")

            return ActionResult.text("\n".join(lines))

        except Exception as e:
            self.logger.error(f"Status action failed: {str(e)}")
            return ActionResult.error(f"Error getting status: {str(e)}")
