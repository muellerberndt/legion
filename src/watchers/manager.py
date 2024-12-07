from typing import Dict, Type, Optional, List
from src.jobs.watcher import WatcherJob
from src.util.logging import Logger
from src.config.config import Config
from src.watchers.webhook_server import WebhookServer
import importlib
import pkgutil
import inspect
import asyncio


class WatcherManager:
    """Manages watcher jobs and their lifecycle"""

    def __init__(self):
        self.logger = Logger("WatcherManager")
        self.config = Config()
        self.watchers: Dict[str, WatcherJob] = {}
        self.webhook_server: Optional[WebhookServer] = None

    def _discover_watchers(self) -> Dict[str, Type[WatcherJob]]:
        """Discover all available watcher classes"""
        watcher_classes = {}

        # Import all modules in the watchers package
        watcher_package = importlib.import_module("src.watchers")
        for _, name, _ in pkgutil.iter_modules(watcher_package.__path__):
            if name != "manager" and name != "webhook_server":
                module = importlib.import_module(f"src.watchers.{name}")
                for item_name, item in inspect.getmembers(module):
                    if inspect.isclass(item) and issubclass(item, WatcherJob) and item != WatcherJob:
                        watcher_classes[name] = item

        return watcher_classes

    async def start(self) -> None:
        """Start enabled watchers based on configuration"""
        watcher_config = self.config.get("watchers", {})

        # If watchers section is missing or enabled is not explicitly set, don't start watchers
        if not watcher_config or "enabled" not in watcher_config:
            self.logger.info("No watcher configuration found, watchers disabled")
            return

        # Check if watchers are explicitly enabled
        if not watcher_config.get("enabled"):
            self.logger.info("Watchers disabled in config")
            return

        # Get active watchers from config, default to empty list
        active_watchers = watcher_config.get("active_watchers", [])
        if not active_watchers:
            self.logger.info("No active watchers configured")
            return

        # Get webhook server instance first
        webhook_port = watcher_config.get("webhook_port", 8080)
        self.webhook_server = await WebhookServer.get_instance()

        # Discover and initialize enabled watchers
        watcher_classes = self._discover_watchers()
        start_tasks = []

        for watcher_name in active_watchers:
            if watcher_name in watcher_classes:
                try:
                    # Create and initialize watcher
                    watcher = watcher_classes[watcher_name]()
                    await watcher.initialize()
                    self.watchers[watcher_name] = watcher

                    # Register webhook routes if supported
                    if hasattr(watcher, "register_routes") and self.webhook_server:
                        watcher.register_routes(self.webhook_server.app)
                        self.logger.info(f"Registered webhook routes for {watcher_name}")

                    # Start watcher in background
                    start_tasks.append(watcher.start())
                    self.logger.info(f"Initialized watcher: {watcher_name}")
                except Exception as e:
                    self.logger.error(f"Failed to initialize watcher {watcher_name}: {e}")
            else:
                self.logger.warning(f"Watcher {watcher_name} not found")

        # Start all watchers concurrently
        if start_tasks:
            try:
                await asyncio.gather(*start_tasks)
                for name in self.watchers:
                    self.logger.info(f"Started watcher: {name}")
            except Exception as e:
                self.logger.error(f"Failed to start watchers: {e}")

        # Start webhook server after all endpoints are registered
        await self.webhook_server.start(webhook_port)

    async def stop(self) -> None:
        """Stop all running watchers"""
        stop_tasks = []

        # Stop all watchers
        for name, watcher in self.watchers.items():
            self.logger.info(f"Stopping watcher: {name}")
            stop_tasks.append(watcher.stop())

        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)

        # Stop webhook server
        if self.webhook_server:
            await self.webhook_server.stop()

        self.watchers.clear()

    def get_watcher(self, name: str) -> Optional[WatcherJob]:
        """Get a running watcher by name"""
        return self.watchers.get(name)

    def list_watchers(self) -> List[str]:
        """List names of all running watchers"""
        return list(self.watchers.keys())
