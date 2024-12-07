from typing import Dict, List, Type
from src.handlers.base import Handler, HandlerTrigger
from src.util.logging import Logger
from src.handlers.event_bus import EventBus
from src.handlers.builtin import get_builtin_handlers

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
        
        # Register built-in handlers
        for handler_class in get_builtin_handlers():
            self.register_handler(handler_class)
            self.logger.info(f"Registered built-in handler: {handler_class.__name__}")
    
    def register_handler(self, handler_class: Type[Handler]) -> None:
        """Register a handler"""
        self.event_bus.register_handler(handler_class)
        
    async def trigger_event(self, trigger: HandlerTrigger, context: Dict) -> None:
        """Trigger handlers for a specific event"""
        await self.event_bus.trigger_event(trigger, context) 