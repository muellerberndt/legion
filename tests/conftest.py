# Mock config before any imports
import os
import pytest
from unittest.mock import patch, Mock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from src.config.config import Config


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

    with patch("src.backend.database.db", mock_db):
        yield mock_db


@pytest.fixture
def mock_test_config():
    """Mock config for non-config tests."""
    mock_config_data = {
        "database": {"host": "localhost", "port": 5432, "name": "test_db", "user": "test", "password": "test"},
        "block_explorers": {
            "etherscan": {"key": None},
            "basescan": {"key": None},
            "arbiscan": {"key": None},
            "polygonscan": {"key": None},
            "bscscan": {"key": None},
        },
        "llm": {"openai": {"key": "test-key", "model": "gpt-4"}},
    }

    # Store original values
    original_config = os.environ.get("R4DAR_CONFIG")
    original_openai_key = os.environ.get("OPENAI_API_KEY")

    # Set test values
    os.environ["R4DAR_CONFIG"] = "/tmp/nonexistent_config.yml"
    os.environ["OPENAI_API_KEY"] = "test-key"

    # Reset config singleton
    Config._instance = None
    Config._config = None

    with patch("src.config.config.load_config", return_value=mock_config_data):
        yield mock_config_data

    # Restore original values
    if original_config:
        os.environ["R4DAR_CONFIG"] = original_config
    else:
        del os.environ["R4DAR_CONFIG"]

    if original_openai_key:
        os.environ["OPENAI_API_KEY"] = original_openai_key
    else:
        del os.environ["OPENAI_API_KEY"]

    # Reset config singleton
    Config._instance = None
    Config._config = None


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
