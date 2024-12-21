"""Webhook server that routes incoming webhooks to appropriate handlers"""

from aiohttp import web
from typing import Dict
from src.util.logging import Logger
from src.webhooks.handlers import WebhookHandler
import asyncio


class WebhookServer:
    """Server that handles incoming webhooks"""

    _instance = None
    _lock = asyncio.Lock()

    def __init__(self):
        self.logger = Logger("WebhookServer")
        self.app = web.Application(middlewares=[self.log_middleware])
        self.runner = None
        self.port = 8080  # Default port
        self.handlers: Dict[str, WebhookHandler] = {}

        # Don't auto-register handlers in init
        # Let the application explicitly register them

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

        # Remove existing route if it exists
        if path in self.handlers:
            self.logger.info(f"Replacing existing handler for path: {path}")
            # Note: aiohttp doesn't provide a way to remove routes, so we'll need to create a new application
            old_middlewares = self.app.middlewares
            self.app = web.Application(middlewares=old_middlewares)

            # Re-register all handlers except the one we're replacing
            for p, h in self.handlers.items():
                if p != path:
                    self.app.router.add_post(p, self._handle_webhook)

        self.logger.info(f"Registering webhook handler for path: {path}")
        self.handlers[path] = handler
        self.app.router.add_post(path, self._handle_webhook)

    async def _handle_webhook(self, request: web.Request) -> web.Response:
        """Route webhook to appropriate handler"""
        path = request.path
        handler = self.handlers.get(path)
        if not handler:
            self.logger.error(f"No handler registered for path: {path}")
            return web.Response(text=f"No handler registered for path: {path}", status=404)

        try:
            self.logger.info(f"Routing request to handler: {type(handler).__name__}")
            response = await handler.handle(request)
            self.logger.info("Handler response", extra_data={"status": response.status, "headers": dict(response.headers)})
            return response
        except Exception as e:
            self.logger.error(f"Error in handler: {str(e)}")
            return web.Response(text=str(e), status=500)

    async def start(self, port: int = 8080) -> None:
        """Start the webhook server"""
        if self.runner:
            self.logger.warning("Webhook server already running")
            return

        self.port = port

        # Log registered handlers
        self.logger.info(
            "Starting webhook server with handlers:",
            extra_data={
                "paths": list(self.handlers.keys()),
                "handler_types": {path: type(handler).__name__ for path, handler in self.handlers.items()},
            },
        )

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
        self.logger.info("\nWebhook URLs:")
        for path in self.handlers.keys():
            self.logger.info(f"  http://localhost:{self.port}{path}")

    async def stop(self) -> None:
        """Stop the webhook server"""
        if self.runner:
            await self.runner.cleanup()
            self.runner = None

    @web.middleware
    async def log_middleware(self, request: web.Request, handler):
        """Log middleware to track request/response cycle"""
        self.logger.info(
            "Incoming request",
            extra_data={
                "method": request.method,
                "path": request.path,
                "headers": dict(request.headers),
                "content_type": request.content_type,
            },
        )
        response = await handler(request)
        self.logger.info("Outgoing response", extra_data={"status": response.status, "headers": dict(response.headers)})
        return response
