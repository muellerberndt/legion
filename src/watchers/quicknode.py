from typing import Dict, Any, List
from src.jobs.watcher import WatcherJob
from src.handlers.base import HandlerTrigger
from src.util.logging import Logger
from src.handlers.registry import HandlerRegistry
from aiohttp import web


class QuicknodeWatcher(WatcherJob):
    """Watcher that handles Quicknode webhook notifications"""

    def __init__(self):
        super().__init__("quicknode", interval=0)  # No polling interval needed for webhooks
        self.logger = Logger("QuicknodeWatcher")
        self.handler_registry = HandlerRegistry()

    async def initialize(self) -> None:
        """Nothing to initialize for webhook-based watcher"""

    async def check(self) -> List[Dict[str, Any]]:
        """Not used for webhook-based watcher"""
        return []

    async def handle_webhook(self, request: web.Request) -> web.Response:
        """Handle incoming webhook from Quicknode

        Args:
            request: The webhook request

        Returns:
            Response to send back to Quicknode
        """
        try:
            # Parse webhook payload
            payload = await request.json()
            self.logger.info("Received Quicknode webhook", extra_data={"payload": payload})

            # Extract events from payload (Quicknode sends a list of events)
            events = payload.get("payload", []) if isinstance(payload, dict) else payload
            if not isinstance(events, list):
                events = [events]

            # Trigger blockchain event for each event
            for event in events:
                await self.handler_registry.trigger_event(
                    HandlerTrigger.BLOCKCHAIN_EVENT, {"source": "quicknode", "payload": event}
                )

            return web.Response(text="OK")

        except Exception as e:
            self.logger.error(f"Error handling Quicknode webhook: {str(e)}")
            return web.Response(text=str(e), status=500)

    def register_routes(self, app: web.Application) -> None:
        """Register webhook route

        Args:
            app: The web application to register routes with
        """
        app.router.add_post("/webhooks/quicknode", self.handle_webhook)
