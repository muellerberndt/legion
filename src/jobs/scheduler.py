"""Scheduler for recurring actions"""

import asyncio
from typing import Dict, Optional
from datetime import datetime, timedelta
from src.util.logging import Logger
from src.config.config import Config
from src.backend.database import DBSessionMixin


class ScheduledAction:
    """Configuration for a scheduled action"""

    def __init__(self, name: str, command: str, interval_minutes: int, enabled: bool = True):
        self.name = name
        self.command = command  # The action command to execute (e.g. "immunefi")
        self.interval_minutes = interval_minutes
        self.enabled = enabled
        self.last_run: Optional[datetime] = None
        self._task: Optional[asyncio.Task] = None


class Scheduler(DBSessionMixin):
    """Manages scheduled actions"""

    _instance = None
    _lock = asyncio.Lock()

    def __init__(self):
        super().__init__()
        self.logger = Logger("Scheduler")
        self.config = Config()
        self.scheduled_actions: Dict[str, ScheduledAction] = {}
        self._running = False
        self._action_registry = None

    @classmethod
    async def get_instance(cls) -> "Scheduler":
        """Get or create the singleton scheduler instance"""
        async with cls._lock:
            if not cls._instance:
                cls._instance = cls()
            return cls._instance

    def _get_action_registry(self):
        """Lazy load action registry to avoid circular imports"""
        if self._action_registry is None:
            from src.actions.registry import ActionRegistry

            self._action_registry = ActionRegistry()
        return self._action_registry

    def load_config(self) -> None:
        """Load scheduled actions from config"""
        scheduled_actions = self.config.get("scheduled_actions", {})
        for name, config in scheduled_actions.items():
            self.schedule_action(
                name=name,
                command=config["command"],
                interval_minutes=config["interval_minutes"],
                enabled=config.get("enabled", True),
            )

    def schedule_action(self, name: str, command: str, interval_minutes: int, enabled: bool = True) -> None:
        """Schedule an action to run at regular intervals"""
        # Verify the action exists
        action_name = command.split()[0]
        if not self._get_action_registry().get_action(action_name):
            self.logger.error(f"Cannot schedule unknown action: {command}")
            return

        self.scheduled_actions[name] = ScheduledAction(name, command, interval_minutes, enabled)
        self.logger.info(f"Scheduled action {name} ({command}) to run every {interval_minutes} minutes")

    def enable_action(self, name: str) -> bool:
        """Enable a scheduled action"""
        if name not in self.scheduled_actions:
            return False
        action = self.scheduled_actions[name]
        action.enabled = True
        if not action._task and self._running:
            action._task = asyncio.create_task(self._schedule_loop(action))
        self.logger.info(f"Enabled scheduled action: {name}")
        return True

    def disable_action(self, name: str) -> bool:
        """Disable a scheduled action"""
        if name not in self.scheduled_actions:
            return False
        action = self.scheduled_actions[name]
        action.enabled = False
        if action._task:
            action._task.cancel()
            action._task = None
        self.logger.info(f"Disabled scheduled action: {name}")
        return True

    def get_action_status(self, name: str) -> Optional[dict]:
        """Get status of a scheduled action"""
        action = self.scheduled_actions.get(name)
        if not action:
            return None
        return {
            "name": action.name,
            "command": action.command,
            "enabled": action.enabled,
            "interval_minutes": action.interval_minutes,
            "last_run": action.last_run.isoformat() if action.last_run else None,
            "next_run": (
                (action.last_run + timedelta(minutes=action.interval_minutes)).isoformat() if action.last_run else None
            ),
        }

    def list_actions(self) -> Dict[str, dict]:
        """List all scheduled actions and their status"""
        return {name: self.get_action_status(name) for name in self.scheduled_actions}

    async def _run_action(self, action: ScheduledAction) -> None:
        """Run a scheduled action"""
        try:
            # Get the action handler
            command_parts = action.command.split()
            action_name = command_parts[0]
            action_args = command_parts[1:]

            action_handler = self._get_action_registry().get_action(action_name)
            if not action_handler:
                self.logger.error(f"Action not found: {action_name}")
                return

            # Execute the action
            handler, _ = action_handler
            result = await handler(*action_args)
            self.logger.info(f"Executed scheduled action {action.name}: {result}")

            # Update last run time
            action.last_run = datetime.utcnow()

        except Exception as e:
            self.logger.error(f"Error running scheduled action {action.name}: {str(e)}")

    async def _schedule_loop(self, action: ScheduledAction) -> None:
        """Main loop for a scheduled action"""
        while self._running and action.enabled:
            try:
                await self._run_action(action)
                # Sleep until next run
                await asyncio.sleep(action.interval_minutes * 60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in schedule loop for {action.name}: {str(e)}")
                await asyncio.sleep(60)  # Wait a bit before retrying

    async def start(self) -> None:
        """Start the scheduler"""
        self._running = True
        self.logger.info("Starting scheduler")

        # Load scheduled actions from config
        self.load_config()

        # Start enabled actions
        for action in self.scheduled_actions.values():
            if action.enabled:
                action._task = asyncio.create_task(self._schedule_loop(action))

    async def stop(self) -> None:
        """Stop the scheduler"""
        self._running = False
        self.logger.info("Stopping scheduler")

        # Cancel all running tasks
        for action in self.scheduled_actions.values():
            if action._task:
                action._task.cancel()
                action._task = None
