from typing import Dict, List, Type
from src.handlers.base import Handler, HandlerTrigger
from src.util.logging import Logger
from src.handlers.asset_revision import AssetRevisionHandler
from src.handlers.event_bus import EventBus

class HandlerRegistry:
    """Registry for event handlers"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HandlerRegistry, cls).__new__(cls)
            cls._instance.initialize()
        return cls._instance
    
    def initialize(self):
        self.logger = Logger("HandlerRegistry")
        self.event_bus = EventBus()
        
        # Register default handlers
        self.register_handler(AssetRevisionHandler)
    
    def register_handler(self, handler_class: Type[Handler]) -> None:
        """Register a handler"""
        self.event_bus.register_handler(handler_class)
        
    async def trigger_event(self, trigger: HandlerTrigger, context: Dict) -> None:
        """Trigger handlers for a specific event"""
        await self.event_bus.trigger_event(trigger, context) 