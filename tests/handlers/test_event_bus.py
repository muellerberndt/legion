import pytest
from unittest.mock import AsyncMock, patch
from src.handlers.event_bus import EventBus
from src.handlers.base import Handler, HandlerTrigger, HandlerResult
from src.models.event_log import EventLog
from src.backend.database import db


@pytest.fixture
def event_bus():
    """Create a fresh EventBus instance for each test"""
    bus = EventBus()
    bus._instance = None
    bus.initialize()
    return bus


@pytest.mark.asyncio
async def test_handler_result_logging(event_bus, mock_database):
    """Test that handler results are properly logged"""

    class TestHandler(Handler):
        @classmethod
        def get_triggers(cls):
            return [HandlerTrigger.NEW_PROJECT]

        async def handle(self):
            return HandlerResult(success=True, data={"test": "data"})

    # Mock the database session
    mock_log_session = AsyncMock()
    mock_log_session.add = AsyncMock()
    mock_log_session.commit = AsyncMock()

    with patch.object(db, "session") as mock_session:
        mock_session.return_value.__enter__.return_value = mock_log_session

        # Register test handler
        event_bus.register_handler(TestHandler)

        # Trigger event
        await event_bus.trigger_event(HandlerTrigger.NEW_PROJECT, {"test": "context"})

        # Verify log was created
        mock_session = mock_database.session.return_value.__enter__.return_value
        assert mock_session.add.called
        log = mock_session.add.call_args[0][0]
        assert isinstance(log, EventLog)
        assert log.handler_name == "TestHandler"
        assert log.trigger == "NEW_PROJECT"
        assert log.result == {"success": True, "data": {"test": "data"}}


@pytest.mark.asyncio
async def test_handler_error_logging(event_bus, mock_database):
    """Test that handler errors are properly logged"""

    class ErrorHandler(Handler):
        @classmethod
        def get_triggers(cls):
            return [HandlerTrigger.NEW_PROJECT]

        async def handle(self):
            raise Exception("Test error")

    # Mock the database session
    mock_log_session = AsyncMock()
    mock_log_session.add = AsyncMock()
    mock_log_session.commit = AsyncMock()

    with patch.object(db, "session") as mock_session:
        mock_session.return_value.__enter__.return_value = mock_log_session

        # Register error handler
        event_bus.register_handler(ErrorHandler)

        # Trigger event
        await event_bus.trigger_event(HandlerTrigger.NEW_PROJECT, {"test": "context"})

        # Verify error log was created
        mock_session = mock_database.session.return_value.__enter__.return_value
        assert mock_session.add.called
        log = mock_session.add.call_args[0][0]
        assert isinstance(log, EventLog)
        assert log.handler_name == "ErrorHandler"
        assert log.trigger == "NEW_PROJECT"
        assert log.result == {"success": False, "error": "Test error"}


@pytest.mark.asyncio
async def test_multiple_handlers_logging(event_bus, mock_database):
    """Test logging with multiple handlers"""

    class TestHandler(Handler):
        @classmethod
        def get_triggers(cls):
            return [HandlerTrigger.NEW_PROJECT]

        async def handle(self):
            return HandlerResult(success=True, data={"test": "data"})

    class ErrorHandler(Handler):
        @classmethod
        def get_triggers(cls):
            return [HandlerTrigger.NEW_PROJECT]

        async def handle(self):
            raise Exception("Test error")

    # Mock the database session
    mock_log_session = AsyncMock()
    mock_log_session.add = AsyncMock()
    mock_log_session.commit = AsyncMock()

    with patch.object(db, "session") as mock_session:
        mock_session.return_value.__enter__.return_value = mock_log_session

        # Register both handlers
        event_bus.register_handler(TestHandler)
        event_bus.register_handler(ErrorHandler)

        # Trigger event
        await event_bus.trigger_event(HandlerTrigger.NEW_PROJECT, {"test": "context"})

        # Get only EventLog entries from the mock calls
        mock_session = mock_database.session.return_value.__enter__.return_value
        event_logs = [call[0][0] for call in mock_session.add.call_args_list if isinstance(call[0][0], EventLog)]
        assert len(event_logs) == 2, f"Expected 2 event logs, got {len(event_logs)}"

        # First log should be from TestHandler
        assert event_logs[0].handler_name == "TestHandler"
        assert event_logs[0].result == {"success": True, "data": {"test": "data"}}

        # Second log should be from ErrorHandler
        assert event_logs[1].handler_name == "ErrorHandler"
        assert event_logs[1].result == {"success": False, "error": "Test error"}


@pytest.mark.asyncio
async def test_handler_without_result(event_bus, mock_database):
    """Test logging when handler returns no result"""

    class NoResultHandler(Handler):
        @classmethod
        def get_triggers(cls):
            return [HandlerTrigger.NEW_PROJECT]

        async def handle(self):
            return None

    # Mock the database session
    mock_log_session = AsyncMock()
    mock_log_session.add = AsyncMock()
    mock_log_session.commit = AsyncMock()

    with patch.object(db, "session") as mock_session:
        mock_session.return_value.__enter__.return_value = mock_log_session

        # Register handler
        event_bus.register_handler(NoResultHandler)

        # Trigger event
        await event_bus.trigger_event(HandlerTrigger.NEW_PROJECT, {"test": "context"})

        # Verify log was created with null result
        mock_session = mock_database.session.return_value.__enter__.return_value
        assert mock_session.add.called
        log = mock_session.add.call_args[0][0]
        assert isinstance(log, EventLog)
        assert log.handler_name == "NoResultHandler"
        assert log.result == {"success": True, "data": None}
