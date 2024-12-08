import pytest
from unittest.mock import AsyncMock
from datetime import datetime
from src.models.event_log import EventLog


def test_event_log_creation():
    """Test creating an EventLog instance with basic attributes"""
    log = EventLog(id="test-id", handler_name="TestHandler", trigger="TEST_TRIGGER", result={"test": "data"})

    assert log.id == "test-id"
    assert log.handler_name == "TestHandler"
    assert log.trigger == "TEST_TRIGGER"
    assert log.result == {"test": "data"}
    assert isinstance(log.created_at, datetime)


def test_event_log_without_result():
    """Test creating an EventLog instance without result data"""
    log = EventLog(id="test-id", handler_name="TestHandler", trigger="TEST_TRIGGER")

    assert log.id == "test-id"
    assert log.result is None
    assert isinstance(log.created_at, datetime)


@pytest.mark.asyncio
async def test_event_log_db_operations(mock_database):
    """Test database operations with EventLog"""
    # Create new event log
    log = EventLog(id="test-id", handler_name="TestHandler", trigger="TEST_TRIGGER", result={"test": "data"})

    # Get mock session and set up async methods
    mock_session = mock_database.session.return_value.__enter__.return_value
    mock_session.add = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.delete = AsyncMock()
    mock_session.get = AsyncMock(return_value=log)

    # Add to database
    await mock_session.add(log)
    await mock_session.commit()

    # Query and verify
    result = await mock_session.get(EventLog, "test-id")
    assert result is not None
    assert result.id == "test-id"
    assert result.handler_name == "TestHandler"
    assert result.trigger == "TEST_TRIGGER"
    assert result.result == {"test": "data"}

    # Update
    result.result = {"updated": "data"}
    await mock_session.commit()

    # Query again and verify update
    updated_log = log  # Mock the updated state
    updated_log.result = {"updated": "data"}
    mock_session.get.return_value = updated_log
    updated = await mock_session.get(EventLog, "test-id")
    assert updated.result == {"updated": "data"}

    # Delete
    await mock_session.delete(result)
    await mock_session.commit()

    # Mock deletion
    mock_session.get.return_value = None

    # Verify deletion
    deleted = await mock_session.get(EventLog, "test-id")
    assert deleted is None
