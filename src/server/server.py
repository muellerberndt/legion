import asyncio
import signal
from typing import Dict, List
from src.jobs.manager import JobManager
from src.watchers.manager import WatcherManager
from src.handlers.registry import HandlerRegistry
from src.util.logging import Logger
from src.config.config import Config
from src.interfaces.base import Interface
from src.interfaces.telegram import TelegramInterface
from src.actions.registry import ActionRegistry
from src.server.extension_loader import ExtensionLoader
from src.handlers.github_events import GitHubEventHandler
import os


class Server:
    """Main server that manages jobs, watchers, and handlers"""

    def __init__(self):
        self.logger = Logger("Server")
        self.config = Config()
        self.job_manager = JobManager()
        self.watcher_manager = WatcherManager()
        self.handler_registry = HandlerRegistry()
        self.action_registry = ActionRegistry()
        self.extension_loader = ExtensionLoader()
        self.interfaces: Dict[str, Interface] = {}
        self.shutdown_event = asyncio.Event()
        self.shutting_down = False

    async def start(self, enabled_interfaces: List[str] = ["telegram"]) -> None:
        """Start the server and all its components"""
        self.logger.info("Starting server...")

        # Register signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.handle_signal(s)))

        try:
            # Start job manager first
            self.logger.info("Starting job manager...")
            await self.job_manager.start()

            # Register built-in handlers
            self.logger.info("Registering built-in handlers...")
            self.handler_registry.register_handler(GitHubEventHandler)

            # Load and register extensions
            self.extension_loader.load_extensions()
            self.extension_loader.register_components()

            # Initialize interfaces
            if "telegram" in enabled_interfaces:
                telegram = TelegramInterface(action_registry=self.action_registry)
                self.interfaces["telegram"] = telegram
                await telegram.start()

                # Register TelegramService for job notifications
                from src.jobs.notification import JobNotifier

                telegram_service = telegram.service
                JobNotifier.register_service(telegram_service)

                self.logger.info("Started Telegram interface")

            # Start watcher manager if enabled
            if self.config.get("watchers", {}).get("enabled", True):
                await self.watcher_manager.start()

            self.logger.info("Server started successfully")

        except Exception as e:
            self.logger.error(f"Server error: {e}")
            raise

    async def handle_signal(self, sig: signal.Signals) -> None:
        """Handle shutdown signals"""
        if self.shutting_down:
            self.logger.warning("Received another shutdown signal, forcing immediate shutdown")
            # Force exit
            os._exit(1)
            return

        self.logger.info(f"Received signal {sig.name}, initiating shutdown...")
        await self.shutdown()
        # Force exit after shutdown attempt
        os._exit(0)

    async def shutdown(self) -> None:
        """Gracefully shutdown the server"""
        if self.shutting_down:
            return

        self.shutting_down = True
        self.logger.info("Shutting down server...")

        try:
            # Stop interfaces first
            for name, interface in self.interfaces.items():
                self.logger.info(f"Stopping interface: {name}")
                try:
                    await asyncio.wait_for(interface.stop(), timeout=2.0)
                except asyncio.TimeoutError:
                    self.logger.error(f"Timeout stopping interface: {name}")

            # Stop watchers
            try:
                await asyncio.wait_for(self.watcher_manager.stop(), timeout=2.0)
            except asyncio.TimeoutError:
                self.logger.error("Timeout stopping watcher manager")

            # Stop job manager last
            try:
                await asyncio.wait_for(self.job_manager.stop(), timeout=2.0)
            except asyncio.TimeoutError:
                self.logger.error("Timeout stopping job manager")

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

    @classmethod
    async def run(cls, enabled_interfaces: List[str] = ["telegram"]) -> None:
        """Run the server"""
        server = cls()
        try:
            await server.start(enabled_interfaces)
            # Keep the server running
            while True:
                try:
                    await asyncio.sleep(1)
                except asyncio.CancelledError:
                    break
        except KeyboardInterrupt:
            await server.shutdown()
        finally:
            await server.shutdown()
