from typing import Dict, List, Type
import asyncio
from src.handlers.base import Handler, HandlerTrigger
from src.util.logging import Logger
from src.models.event_log import EventLog
from src.backend.database import DBSessionMixin
import uuid


class EventBus(DBSessionMixin):
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
            self.logger.debug(f"Registered {handler_class.__name__} for trigger {trigger.name}")

    async def trigger_event(self, trigger: HandlerTrigger, context: Dict) -> None:
        """Trigger handlers for a specific event"""
        if trigger not in self._handlers:
            self.logger.warning(f"No handlers registered for trigger {trigger.name}")
            return

        self.logger.info(f"Triggering {len(self._handlers[trigger])} handlers for {trigger.name}")

        handler_tasks = []
        for handler_class in self._handlers[trigger]:
            try:
                self.logger.debug(f"Creating handler instance for {handler_class.__name__}")
                handler = handler_class()
                handler.set_context(context, trigger)
                handler_tasks.append(self._execute_handler(handler, trigger))
            except Exception as e:
                self.logger.error(
                    f"Handler {handler_class.__name__} failed: {str(e)}",
                    extra_data={"trigger": trigger.name, "context": context},
                )

        # Wait for all handlers to complete
        if handler_tasks:
            await asyncio.gather(*handler_tasks, return_exceptions=True)

    async def _execute_handler(self, handler: Handler, trigger: HandlerTrigger) -> None:
        """Execute a handler and log the result"""
        try:
            result = await handler.handle()

            # Create event log
            log = EventLog(
                id=str(uuid.uuid4()),
                handler_name=handler.__class__.__name__,
                trigger=trigger.name,
                result={"success": result.success if result else True, "data": result.data if result else None},
            )

            # Save to database
            async with self.get_session() as session:
                await session.add(log)
                await session.commit()

        except Exception as e:
            self.logger.error(f"Handler execution failed: {str(e)}")
            # Log error result
            log = EventLog(
                id=str(uuid.uuid4()),
                handler_name=handler.__class__.__name__,
                trigger=trigger.name,
                result={"success": False, "error": str(e)},
            )
            async with self.get_session() as session:
                await session.add(log)
                await session.commit()
