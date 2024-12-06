from typing import Dict, List, Type
import asyncio
from src.handlers.base import Handler, HandlerTrigger
from src.util.logging import Logger

class EventBus:
    """Central event bus for triggering handlers"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
            cls._instance.initialize()
        return cls._instance
    
    def initialize(self):
        self.logger = Logger("EventBus")
        self._handlers: Dict[HandlerTrigger, List[Type[Handler]]] = {}
    
    def register_handler(self, handler_class: Type[Handler]) -> None:
        """Register a handler for specific triggers"""
        for trigger in handler_class.get_triggers():
            if trigger not in self._handlers:
                self._handlers[trigger] = []
            self._handlers[trigger].append(handler_class)
            
    async def trigger_event(self, trigger: HandlerTrigger, context: Dict) -> None:
        """Trigger handlers for a specific event"""
        if trigger not in self._handlers:
            return
            
        self.logger.info(f"Triggering {trigger.value} handlers", extra_data={'context': context})
        
        handler_tasks = []
        for handler_class in self._handlers[trigger]:
            try:
                handler = handler_class()
                handler.set_context(context)
                handler_tasks.append(asyncio.create_task(handler.handle()))
            except Exception as e:
                self.logger.error(
                    f"Handler {handler_class.__name__} failed: {str(e)}",
                    extra_data={'trigger': trigger.value, 'context': context}
                )
                
        # Wait for all handlers to complete
        if handler_tasks:
            await asyncio.gather(*handler_tasks, return_exceptions=True) 