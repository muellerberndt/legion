import asyncio
from typing import List
from src.util.logging import Logger
from src.server.initialization import Initializer
from src.jobs.manager import JobManager
from src.server.extension_loader import ExtensionLoader
from src.webhooks.server import WebhookServer
from src.jobs.scheduler import Scheduler
from src.config.config import Config
from src.webhooks.handlers import QuicknodeWebhookHandler
from src.jobs.notification import JobNotifier
from src.services.db_notification_service import DatabaseNotificationService


class Server:
    """Main server class that coordinates all components"""

    @classmethod
    async def run(cls) -> None:
        """Run the server"""
        logger = Logger("Server")
        initializer = Initializer()
        job_manager = JobManager()
        config = Config()
        webhook_enabled = False

        try:
            print("Starting server...")  # Direct console output
            logger.info("Starting server initialization...")

            # Initialize database
            await initializer.init_db()

            # Start webhook server if enabled
            webhook_enabled = config.get("webhook_server.enabled", True)
            if webhook_enabled:
                logger.info("Starting webhook server...")
                webhook_server = await WebhookServer.get_instance()

                # Register webhook handlers
                webhook_server.register_handler("/webhooks/quicknode", QuicknodeWebhookHandler())

                await webhook_server.start()
            else:
                logger.info("Webhook server disabled in config")

            # Load and register extensions
            logger.info("Loading extensions...")
            extension_loader = ExtensionLoader()
            extension_loader.load_extensions()
            await extension_loader.register_components()

            # Start job manager
            logger.info("Starting job manager...")
            await job_manager.start()

            # Register notification services
            JobNotifier.register_service(DatabaseNotificationService())

            # Initialize and start scheduler
            logger.info("Starting scheduler...")
            scheduler = await Scheduler.get_instance()
            await scheduler.start()

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

            # Stop webhook server if it was started
            if webhook_enabled:
                try:
                    webhook_server = await WebhookServer.get_instance()
                    await webhook_server.stop()
                except Exception as e:
                    logger.error(f"Error stopping webhook server: {e}")

            logger.info("Server shutdown complete")
            print("Server shutdown complete")  # Direct console output
