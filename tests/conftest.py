import pytest
from src.config.config import Config
import os
from unittest.mock import patch


@pytest.fixture(autouse=True)
def mock_database():
    """Mock database initialization for all tests."""
    with patch("src.backend.database.Database.__init__", return_value=None):
        yield


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
