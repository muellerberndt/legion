from aiohttp import web
from src.util.logging import Logger
from typing import Optional, Dict, Callable, Awaitable
import asyncio

class WebhookServer:
    """Shared webhook server that watchers can register endpoints with"""
    
    _instance: Optional['WebhookServer'] = None
    _lock = asyncio.Lock()
    
    def __init__(self):
        self.logger = Logger("WebhookServer")
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.port = 8080  # Default port
        
    @classmethod
    async def get_instance(cls) -> 'WebhookServer':
        """Get or create the singleton webhook server instance"""
        async with cls._lock:
            if not cls._instance:
                cls._instance = WebhookServer()
            return cls._instance
            
    def register_endpoint(self, path: str, handler: Callable[[web.Request], Awaitable[web.Response]]) -> None:
        """Register a new webhook endpoint"""
        if not path.startswith('/'):
            path = '/' + path
        if not path.startswith('/webhook/'):
            path = '/webhook' + path
            
        self.logger.info(f"Registering webhook endpoint: {path}")
        self.app.router.add_post(path, handler)
        
    async def start(self, port: int = 8080) -> None:
        """Start the webhook server"""
        if self.runner:
            self.logger.warning("Webhook server already running")
            return
            
        self.port = port
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, '0.0.0.0', self.port)
        await site.start()
        self.logger.info(f"Webhook server listening on port {self.port}")
        
    async def stop(self) -> None:
        """Stop the webhook server"""
        if self.runner:
            await self.runner.cleanup()
            self.runner = None 