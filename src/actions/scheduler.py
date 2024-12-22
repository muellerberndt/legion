"""Action to manage scheduled actions"""

from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.jobs.scheduler import Scheduler
from src.util.logging import Logger
from src.actions.result import ActionResult


class SchedulerAction(BaseAction):
    """Action to manage scheduled actions"""

    spec = ActionSpec(
        name="scheduler",
        description="Manage scheduled actions",
        help_text="""Manage actions that run automatically at configured intervals.

Usage:
/scheduler list                     # List all scheduled actions and their status
/scheduler enable <action_name>     # Enable a scheduled action
/scheduler disable <action_name>    # Disable a scheduled action
/scheduler status <action_name>     # Get detailed status of a scheduled action

Examples:
/scheduler list
/scheduler enable daily_immunefi_sync
/scheduler disable github_sync_4_hours
/scheduler status weekly_embeddings

Scheduled actions are configured in config.yml under the scheduled_actions section.
Each action has a name, command to execute, interval in minutes, and enabled status.""",
        agent_hint="Use this command to manage actions that run automatically at configured intervals",
        arguments=[
            ActionArgument(
                name="command",
                description="Command to execute (list, enable, disable, status)",
                required=True,
            ),
            ActionArgument(
                name="action_name",
                description="Name of the scheduled action to manage",
                required=False,
            ),
        ],
    )

    def __init__(self):
        self.logger = Logger("SchedulerAction")

    async def execute(self, *args) -> ActionResult:
        """Execute the scheduler action"""
        try:
            if not args:
                return ActionResult.error("Please specify a command. Use /help scheduler for usage information.")

            command = args[0].lower()

            if command not in ["list", "enable", "disable", "status"]:
                return ActionResult.error(f"Unknown command: {command}. Use /help scheduler for usage information.")

            scheduler = await Scheduler.get_instance()

            if command == "list":
                actions = scheduler.list_actions()
                if not actions:
                    return ActionResult.text("No scheduled actions configured")

                lines = ["📅 Scheduled Actions:"]
                for name, status in actions.items():
                    enabled = "✅" if status["enabled"] else "❌"
                    interval = f"{status['interval_minutes']} minutes"
                    last_run = status["last_run"] or "Never"
                    lines.append(f"\n{enabled} {name}")
                    lines.append(f"   • Command: {status['command']}")
                    lines.append(f"   • Interval: {interval}")
                    lines.append(f"   • Last run: {last_run}")
                    if status["next_run"]:
                        lines.append(f"   • Next run: {status['next_run']}")
                return ActionResult.text("\n".join(lines))

            if len(args) < 2:
                return ActionResult.error("Please specify an action name")

            action_name = args[1]

            if command == "enable":
                if scheduler.enable_action(action_name):
                    return ActionResult.text(f"✅ Enabled scheduled action: {action_name}")
                return ActionResult.error(f"❌ Action not found: {action_name}")

            elif command == "disable":
                if scheduler.disable_action(action_name):
                    return ActionResult.text(f"✅ Disabled scheduled action: {action_name}")
                return ActionResult.error(f"❌ Action not found: {action_name}")

            elif command == "status":
                status = scheduler.get_action_status(action_name)
                if not status:
                    return ActionResult.error(f"❌ Action not found: {action_name}")

                lines = [f"📊 Status for {action_name}:"]
                lines.append(f"• Command: {status['command']}")
                lines.append(f"• Enabled: {'Yes' if status['enabled'] else 'No'}")
                lines.append(f"• Interval: {status['interval_minutes']} minutes")
                lines.append(f"• Last run: {status['last_run'] or 'Never'}")
                if status["next_run"]:
                    lines.append(f"• Next run: {status['next_run']}")
                return ActionResult.text("\n".join(lines))

        except Exception as e:
            self.logger.error(f"Scheduler action failed: {str(e)}")
            return ActionResult.error(f"Error executing scheduler command: {str(e)}")
