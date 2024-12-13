"""Webhook handlers for different services"""

from abc import ABC, abstractmethod
from aiohttp import web
from src.handlers.base import HandlerTrigger
from src.handlers.registry import HandlerRegistry
from src.util.logging import Logger


class WebhookHandler(ABC):
    """Base class for webhook handlers"""

    def __init__(self):
        self.logger = Logger(self.__class__.__name__)
        self.handler_registry = HandlerRegistry()

    @abstractmethod
    async def handle(self, request: web.Request) -> web.Response:
        """Handle the webhook request"""


class QuicknodeWebhookHandler(WebhookHandler):
    """Handler for Quicknode webhook notifications"""

    async def handle(self, request: web.Request) -> web.Response:
        """Handle incoming webhook from Quicknode"""
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
