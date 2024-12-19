from src.actions.base import BaseAction, ActionSpec
from src.jobs.manager import JobManager
from src.jobs.scheduler import Scheduler
from src.webhooks.server import WebhookServer
from src.util.logging import Logger
from src.actions.result import ActionResult


class StatusAction(BaseAction):
    """Action to show system status"""

    spec = ActionSpec(
        name="status",
        description="Show system status",
        help_text="""Show the current status of the system, including:
- Running jobs
- Scheduled actions
- Webhook server status""",
        agent_hint="Use this command to check the system status",
        arguments=[],
    )

    def __init__(self):
        self.logger = Logger("StatusAction")

    async def execute(self, *args) -> ActionResult:
        """Execute the status action"""
        try:
            lines = []

            # Add running jobs section
            lines.append("🏃 Running Jobs:")
            try:
                # Get job status
                job_manager = await JobManager.get_instance()
                jobs = await job_manager.list_jobs()

                if jobs:
                    for job in jobs:
                        lines.append(f"• {job['id']} ({job['type']}, status: {job['status']})")
                else:
                    lines.append("• No jobs currently running")
            except Exception as e:
                lines.append(f"• Error getting jobs: {str(e)}")

            try:
                # Get scheduled actions status
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

            try:
                # Get webhook status
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
