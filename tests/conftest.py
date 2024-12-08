# isort: skip_file
# flake8: noqa: E402
from unittest.mock import patch, Mock

# Create test config
TEST_CONFIG = {
    "data_dir": "./test_data",
    "database": {"host": "localhost", "port": 5432, "name": "test_db", "user": "test", "password": "test"},
    "block_explorers": {
        "etherscan": {"key": None},
        "basescan": {"key": None},
        "arbiscan": {"key": None},
        "polygonscan": {"key": None},
        "bscscan": {"key": None},
    },
    "llm": {"openai": {"key": "test-key", "model": "gpt-4"}},
    "telegram": {"bot_token": "test-token", "chat_id": "test-chat"},
    "watchers": {"active_watchers": []},
    "extensions_dir": "./test_extensions",
    "active_extensions": [],
}

# Start config patch
config_patcher = patch("src.config.config.load_config", return_value=TEST_CONFIG)
config_patcher.start()

# Now import pytest and other modules
import pytest
from src.config.config import Config


def pytest_configure(config):
    """Configure test environment."""
    # Register custom marks
    config.addinivalue_line("markers", "no_collect: mark a class to prevent collection as a test case")
    Config.set_test_mode(True)


def pytest_unconfigure(config):
    """Clean up test environment."""
    Config.set_test_mode(False)
    config_patcher.stop()


@pytest.fixture(autouse=True)
def setup_test_env(request):
    """Set up test environment."""
    # For config tests, stop the patch temporarily
    if "config/test_config.py" in str(request.node.fspath):
        config_patcher.stop()
        yield
        config_patcher.start()
    else:
        yield


@pytest.fixture(autouse=True)
def mock_database():
    """Mock database for all tests."""
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
    mock_sync_session = Mock()
    mock_sync_session.__enter__ = Mock(return_value=mock_sync_session)
    mock_sync_session.__exit__ = Mock(return_value=None)

    mock_async_session = Mock()
    mock_async_session.__aenter__ = Mock(return_value=mock_async_session)
    mock_async_session.__aexit__ = Mock(return_value=None)

    mock_db.session.return_value.__enter__ = Mock(return_value=mock_sync_session)
    mock_db.session.return_value.__exit__ = Mock(return_value=None)
    mock_db.async_session.return_value.__aenter__ = Mock(return_value=mock_async_session)
    mock_db.async_session.return_value.__aexit__ = Mock(return_value=None)

    with patch("src.backend.database.db", mock_db):
        yield mock_db
