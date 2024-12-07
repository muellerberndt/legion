import pytest
from src.config.config import Config
import os
from unittest.mock import patch, Mock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session


@pytest.fixture(autouse=True)
def mock_database():
    """Mock database initialization for all tests."""
    mock_db = Mock()
    mock_db._engine = Mock()
    mock_db._async_engine = Mock()
    mock_db._SessionLocal = Mock()
    mock_db._AsyncSessionLocal = Mock()
    mock_db.session = Mock()
    mock_db.async_session = Mock()
    mock_db.get_engine = Mock(return_value=Mock())
    mock_db.get_async_engine = Mock(return_value=Mock())
    mock_db.is_initialized = Mock(return_value=True)

    # Create mock session instances
    mock_sync_session = Mock(spec=Session)
    mock_async_session = Mock(spec=AsyncSession)

    # Set up context managers for sessions
    mock_sync_session.__enter__ = Mock(return_value=mock_sync_session)
    mock_sync_session.__exit__ = Mock(return_value=None)
    mock_async_session.__aenter__ = Mock(return_value=mock_async_session)
    mock_async_session.__aexit__ = Mock(return_value=None)

    mock_db.session.return_value.__enter__ = Mock(return_value=mock_sync_session)
    mock_db.session.return_value.__exit__ = Mock(return_value=None)
    mock_db.async_session.return_value.__aenter__ = Mock(return_value=mock_async_session)
    mock_db.async_session.return_value.__aexit__ = Mock(return_value=None)

    with (
        patch("src.backend.database.Database.__new__", return_value=mock_db),
        patch("src.backend.database.Database.__init__", return_value=None),
        patch("src.backend.database.db", mock_db),
    ):
        yield mock_db


@pytest.fixture(autouse=True)
def enable_test_mode():
    """Enable test mode for all tests."""
    Config.set_test_mode(True)
    yield
    Config.set_test_mode(False)  # Reset after test


@pytest.fixture(autouse=True)
def reset_config():
    """Reset config singleton between tests."""
    # Store original values
    original_config = os.environ.get("R4DAR_CONFIG")
    original_db_url = os.environ.get("DATABASE_URL")

    # Clear config
    Config._instance = None
    Config._config = None

    # Clear environment variables
    for key in list(os.environ.keys()):
        if key.startswith("R4DAR_") or key == "DATABASE_URL":
            del os.environ[key]

    yield

    # Restore original values
    if original_config:
        os.environ["R4DAR_CONFIG"] = original_config
    if original_db_url:
        os.environ["DATABASE_URL"] = original_db_url

    # Clean up
    Config._instance = None
    Config._config = None
