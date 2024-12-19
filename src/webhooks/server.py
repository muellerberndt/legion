"""Webhook server that routes incoming webhooks to appropriate handlers"""

from aiohttp import web
from typing import Dict
from src.util.logging import Logger
from src.webhooks.handlers import WebhookHandler, QuicknodeWebhookHandler
import asyncio


class WebhookServer:
    """Server that handles incoming webhooks"""

    _instance = None
    _lock = asyncio.Lock()

    def __init__(self):
        self.logger = Logger("WebhookServer")
        self.app = web.Application()
        self.runner = None
        self.port = 8080  # Default port
        self.handlers: Dict[str, WebhookHandler] = {}

        # Register built-in handlers
        self.register_handler("/webhooks/quicknode", QuicknodeWebhookHandler())

    @classmethod
    async def get_instance(cls) -> "WebhookServer":
        """Get or create the singleton webhook server instance"""
        async with cls._lock:
            if not cls._instance:
                cls._instance = WebhookServer()
            return cls._instance

    def register_handler(self, path: str, handler: WebhookHandler) -> None:
        """Register a webhook handler for a specific path"""
        if not path.startswith("/"):
            path = "/" + path
        if not path.startswith("/webhooks/"):
            path = "/webhooks" + path

        self.logger.info(f"Registering webhook handler for path: {path}")
        self.handlers[path] = handler
        self.app.router.add_post(path, self._handle_webhook)

    async def _handle_webhook(self, request: web.Request) -> web.Response:
        """Route webhook to appropriate handler"""
        path = request.path
        handler = self.handlers.get(path)
        if not handler:
            return web.Response(text=f"No handler registered for path: {path}", status=404)

        return await handler.handle(request)

    async def start(self, port: int = 8080) -> None:
        """Start the webhook server"""
        if self.runner:
            self.logger.warning("Webhook server already running")
            return

        self.port = port
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "0.0.0.0", self.port)
        await site.start()

        # Add helpful setup instructions
        self.logger.info(f"Webhook server listening on port {self.port}")
        self.logger.info("To expose webhooks to the internet:")
        self.logger.info("1. Install ngrok: brew install ngrok")
        self.logger.info(f"2. Run: ngrok http {self.port}")
        self.logger.info("3. Copy the https:// URL from ngrok output")

        # Log registered webhook paths
        if self.handlers:
            self.logger.info("\nRegistered webhook paths:")
            for path in self.handlers.keys():
                self.logger.info(f"  {path}")

    async def stop(self) -> None:
        """Stop the webhook server"""
        if self.runner:
            await self.runner.cleanup()
            self.runner = None
