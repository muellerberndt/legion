import pytest
from unittest.mock import Mock
from src.handlers.base import Handler, HandlerTrigger
from src.handlers.registry import HandlerRegistry
from src.handlers.event_bus import EventBus


class MockHandler(Handler):
    def __init__(self):
        super().__init__()
        self.handled = False

    async def handle(self) -> None:
        self.handled = True

    @classmethod
    def get_triggers(cls) -> list[HandlerTrigger]:
        return [HandlerTrigger.NEW_PROJECT]


@pytest.fixture
def handler_registry():
    registry = HandlerRegistry()
    # Reset EventBus state
    event_bus = EventBus()
    event_bus._handlers = {}
    event_bus.initialize()
    return registry


def test_singleton_pattern():
    """Test that HandlerRegistry is a singleton"""
    registry1 = HandlerRegistry()
    registry2 = HandlerRegistry()
    assert registry1 is registry2


def test_register_handler(handler_registry):
    """Test handler registration"""
    handler_registry.register_handler(MockHandler)
    event_bus = EventBus()
    assert len(event_bus._handlers.get(HandlerTrigger.NEW_PROJECT, [])) == 1


@pytest.mark.asyncio
async def test_trigger_event(handler_registry):
    """Test event triggering"""
    handler_registry.register_handler(MockHandler)

    context = {"project": Mock()}
    event_bus = EventBus()
    await event_bus.trigger_event(HandlerTrigger.NEW_PROJECT, context)

    # Event should have been handled
    assert len(event_bus._handlers.get(HandlerTrigger.NEW_PROJECT, [])) == 1


@pytest.mark.asyncio
async def test_trigger_event_with_error(handler_registry):
    """Test error handling during event triggering"""

    class ErrorHandler(MockHandler):
        async def handle(self) -> None:
            raise Exception("Test error")

    handler_registry.register_handler(ErrorHandler)
    context = {"project": Mock()}

    # Should not raise exception
    event_bus = EventBus()
    await event_bus.trigger_event(HandlerTrigger.NEW_PROJECT, context)
