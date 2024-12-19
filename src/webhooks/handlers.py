"""Webhook handlers for different services"""

from abc import ABC, abstractmethod
from aiohttp import web
from src.handlers.base import HandlerTrigger
from src.handlers.registry import HandlerRegistry
from src.util.logging import Logger
import json


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

            # Validate basic payload structure
            if not isinstance(payload, dict) or "payload" not in payload:
                return web.Response(text="Invalid payload format: missing 'payload' field", status=400)

            # Extract events from payload
            events = payload.get("payload", [])
            if not isinstance(events, list):
                events = [events]

            # Validate each event
            for event in events:
                if not isinstance(event, dict):
                    return web.Response(text="Invalid event format: must be a dictionary", status=400)

                # Check for required fields
                if "logs" not in event:
                    return web.Response(text="Missing required logs field in event", status=400)

                logs = event.get("logs", [])
                if not isinstance(logs, list) or not logs:
                    return web.Response(text="Invalid or empty logs array", status=400)

                # Validate log structure (for proxy implementation upgrades)
                for log in logs:
                    if not isinstance(log, dict):
                        return web.Response(text="Invalid log format", status=400)
                    if "topics" not in log or not isinstance(log["topics"], list):
                        return web.Response(text="Missing or invalid topics in log", status=400)

            # If validation passes, trigger events
            for event in events:
                await self.handler_registry.trigger_event(
                    HandlerTrigger.BLOCKCHAIN_EVENT, {"source": "quicknode", "payload": event}
                )

            return web.Response(text="OK")

        except json.JSONDecodeError:
            return web.Response(text="Invalid JSON payload", status=400)
        except Exception as e:
            self.logger.error(f"Error handling Quicknode webhook: {str(e)}")
            return web.Response(text=str(e), status=500)
