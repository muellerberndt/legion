import asyncio
from typing import List
from src.interfaces.telegram import TelegramInterface
from src.interfaces.base import Interface
from src.util.logging import Logger
from src.server.initialization import Initializer
from src.watchers.manager import WatcherManager
from src.services.telegram import TelegramService
from src.actions.registry import ActionRegistry
from src.jobs.manager import JobManager


class Server:
    """Main server class that coordinates all components"""

    @classmethod
    async def run(cls, interfaces: List[str]) -> None:
        """Run the server with specified interfaces"""
        logger = Logger("Server")
        initializer = Initializer()
        watcher_manager = WatcherManager.get_instance()
        action_registry = ActionRegistry()
        job_manager = JobManager()

        try:
            print("Starting server...")  # Direct console output
            logger.info("Starting server initialization...")

            # Initialize database
            await initializer.init_db()

            # Start job manager first
            logger.info("Starting job manager...")
            await job_manager.start()

            # Start watchers
            await watcher_manager.start()

            # Initialize interfaces
            interface_instances: List[Interface] = []
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

            # Stop job manager
            try:
                await job_manager.stop()
            except Exception as e:
                logger.error(f"Error stopping job manager: {e}")

            # Stop watchers
            try:
                await watcher_manager.stop()
            except Exception as e:
                logger.error(f"Error stopping watchers: {e}")

            # Cleanup Telegram service
            try:
                telegram_service = TelegramService.get_instance()
                await telegram_service.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up Telegram service: {e}")

            logger.info("Server shutdown complete")
            print("Server shutdown complete")  # Direct console output
