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
            # Verify content type first
            content_type = request.headers.get("Content-Type", "")
            if not content_type or "application/json" not in content_type.lower():
                self.logger.error(
                    "Invalid content type", extra_data={"content_type": content_type, "headers": dict(request.headers)}
                )
                return web.Response(
                    text="Invalid content type - must be application/json", status=400, content_type="text/plain"
                )

            # Parse webhook payload
            try:
                payload = await request.json()
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON parse error: {str(e)}", extra_data={"raw_data": await request.text()})
                return web.Response(text=f"Invalid JSON payload: {str(e)}", status=400)

            # Validate payload structure
            if not isinstance(payload, list):
                self.logger.error("Invalid payload format - must be an array", extra_data={"payload": payload})
                return web.Response(text="Invalid payload format - must be an array", status=400)

            if not payload:  # Empty array
                self.logger.error("Empty payload array")
                return web.Response(text="Empty payload array", status=400)

            # Validate each event
            for event in payload:
                if not isinstance(event, dict):
                    self.logger.error("Invalid event format: must be a dictionary", extra_data={"event": event})
                    return web.Response(text="Invalid event format: must be a dictionary", status=400)

                # Check for required fields in transaction receipt format
                if "logs" not in event:
                    self.logger.error("Missing required logs field in event", extra_data={"event": event})
                    return web.Response(text="Missing required logs field in event", status=400)

                logs = event.get("logs", [])
                if not isinstance(logs, list):
                    self.logger.error("Invalid logs format: must be an array", extra_data={"logs": logs})
                    return web.Response(text="Invalid logs format: must be an array", status=400)

                # Validate log structure
                for log in logs:
                    if not isinstance(log, dict):
                        self.logger.error("Invalid log format", extra_data={"log": log})
                        return web.Response(text="Invalid log format", status=400)
                    if "topics" not in log or not isinstance(log["topics"], list):
                        self.logger.error("Missing or invalid topics in log", extra_data={"log": log})
                        return web.Response(text="Missing or invalid topics in log", status=400)

            # If validation passes, trigger events
            for event in payload:
                await self.handler_registry.trigger_event(
                    HandlerTrigger.BLOCKCHAIN_EVENT, {"source": "quicknode", "payload": event}
                )

            return web.Response(text="OK")

        except Exception as e:
            self.logger.error(f"Error handling Quicknode webhook: {str(e)}")
            return web.Response(text=str(e), status=500)
