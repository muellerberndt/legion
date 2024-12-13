import asyncio
from typing import List
from src.interfaces.telegram import TelegramInterface
from src.interfaces.base import Interface
from src.util.logging import Logger
from src.server.initialization import Initializer
from src.services.telegram import TelegramService
from src.actions.registry import ActionRegistry
from src.jobs.manager import JobManager
from src.server.extension_loader import ExtensionLoader
from src.webhooks.server import WebhookServer
from src.jobs.scheduler import Scheduler
from src.jobs.github_monitor import GithubMonitorJob
from src.jobs.indexer import IndexerJob


class Server:
    """Main server class that coordinates all components"""

    @classmethod
    async def run(cls, interfaces: List[str]) -> None:
        """Run the server with specified interfaces"""
        logger = Logger("Server")
        initializer = Initializer()
        action_registry = ActionRegistry()
        job_manager = JobManager()
        interface_instances: List[Interface] = []

        try:
            print("Starting server...")  # Direct console output
            logger.info("Starting server initialization...")

            # Initialize database
            await initializer.init_db()

            # Start webhook server first (needed for extension registration)
            logger.info("Starting webhook server...")
            webhook_server = await WebhookServer.get_instance()
            await webhook_server.start()

            # Load and register extensions
            logger.info("Loading extensions...")
            extension_loader = ExtensionLoader()
            extension_loader.load_extensions()
            await extension_loader.register_components()

            # Start job manager
            logger.info("Starting job manager...")
            await job_manager.start()

            # Initialize and start scheduler
            logger.info("Starting scheduler...")
            scheduler = await Scheduler.get_instance()

            # Register default scheduled jobs
            scheduler.schedule_job("immunefi_sync", IndexerJob, interval_minutes=60, enabled=True)
            scheduler.schedule_job("github_monitor", GithubMonitorJob, interval_minutes=30, enabled=True)

            await scheduler.start()

            # Initialize interfaces
            for interface_name in interfaces:
                if interface_name == "telegram":
                    interface = TelegramInterface(action_registry=action_registry)
                    interface_instances.append(interface)
                else:
                    logger.warning(f"Unknown interface: {interface_name}")

            # Start interfaces
            for interface in interface_instances:
                await interface.start()

            logger.info("Server started successfully")
            print("Server is running...")  # Direct console output

            # Keep server running
            try:
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                logger.info("Server shutdown initiated")
                raise

        except Exception as e:
            logger.error(f"Server error: {str(e)}")
            print(f"Server error: {str(e)}")  # Direct console output
            raise

        finally:
            # Cleanup
            logger.info("Cleaning up server resources...")
            print("Cleaning up server resources...")  # Direct console output

            # Stop interfaces
            for interface in interface_instances:
                try:
                    await interface.stop()
                except Exception as e:
                    logger.error(f"Error stopping interface: {e}")

            # Stop scheduler
            try:
                await scheduler.stop()
            except Exception as e:
                logger.error(f"Error stopping scheduler: {e}")

            # Stop job manager
            try:
                await job_manager.stop()
            except Exception as e:
                logger.error(f"Error stopping job manager: {e}")

            # Stop webhook server
            try:
                webhook_server = await WebhookServer.get_instance()
                await webhook_server.stop()
            except Exception as e:
                logger.error(f"Error stopping webhook server: {e}")

            # Cleanup Telegram service
            try:
                telegram_service = TelegramService.get_instance()
                await telegram_service.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up Telegram service: {e}")

            logger.info("Server shutdown complete")
            print("Server shutdown complete")  # Direct console output
