from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio
from src.util.logging import Logger
from src.handlers.base import HandlerTrigger
from src.handlers.event_bus import EventBus


class WatcherJob(ABC):
    """Base class for watcher jobs that monitor external states"""

    def __init__(self, name: str, interval: int = 60):
        """Initialize the watcher

        Args:
            name: Name of the watcher for logging
            interval: Check interval in seconds
        """
        self.name = name
        self.interval = interval
        self.logger = Logger(f"Watcher-{name}")
        self.event_bus = EventBus()
        self._stop_event = asyncio.Event()
        self._last_check: Optional[datetime] = None
        self._state: Dict[str, Any] = {}  # Store watcher state
        self._watch_task: Optional[asyncio.Task] = None

    @abstractmethod
    async def check(self) -> List[Dict[str, Any]]:
        """Check for updates and return list of events

        Returns:
            List of event dictionaries with at least:
            - trigger: HandlerTrigger enum value
            - data: Dict of event data
        """

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize watcher state"""

    async def start(self) -> None:
        """Start the watcher loop"""
        try:
            # Don't start if already running
            if self._watch_task and not self._watch_task.done():
                self.logger.warning(f"Watcher {self.name} already running")
                return

            # Initialize watcher if not already initialized
            if self._last_check is None:
                await self.initialize()
            self._last_check = datetime.utcnow()

            # Start the watch loop in a background task if interval > 0
            if self.interval > 0:
                self.logger.info(f"Starting watcher loop for {self.name}")
                self._watch_task = asyncio.create_task(self._watch_loop())
                self._watch_task.add_done_callback(self._on_task_done)
            else:
                self.logger.info(f"Started webhook-based watcher {self.name}")

        except Exception as e:
            error_msg = f"Watcher failed: {str(e)}"
            self.logger.error(error_msg)

    def _on_task_done(self, task: asyncio.Task) -> None:
        """Handle task completion"""
        try:
            # Get the result to handle any exceptions
            task.result()
        except asyncio.CancelledError:
            self.logger.info(f"Watcher {self.name} task cancelled")
        except Exception as e:
            self.logger.error(f"Watcher {self.name} task failed: {str(e)}")

    async def _watch_loop(self) -> None:
        """Background task for the watch loop"""
        while not self._stop_event.is_set():
            try:
                # Check for updates
                events = await self.check()

                # Process events
                for event in events:
                    trigger = event.get("trigger")
                    data = event.get("data", {})

                    if trigger and isinstance(trigger, HandlerTrigger):
                        # Trigger handlers
                        self.event_bus.trigger_event(trigger, data)

                        # Log event
                        self.logger.info(f"Event detected - Trigger: {trigger.name}, " f"Data: {str(data)}")

                # Update last check time
                self._last_check = datetime.utcnow()

            except Exception as e:
                self.logger.error(f"Error in watch cycle: {str(e)}")

            # Wait for next check or stop signal
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval)
            except asyncio.TimeoutError:
                continue

    async def stop(self) -> None:
        """Stop the watcher"""
        self._stop_event.set()

        # Cancel and wait for the watch task
        if self._watch_task and not self._watch_task.done():
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass

    def get_state(self) -> Dict[str, Any]:
        """Get current watcher state"""
        return {
            "name": self.name,
            "last_check": self._last_check.isoformat() if self._last_check else None,
            "running": not self._stop_event.is_set(),
            "state": self._state,
        }
