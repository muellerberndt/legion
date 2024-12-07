import os
import pytest
from unittest.mock import patch, Mock
import yaml
from src.config.config import Config


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


@pytest.fixture(autouse=True)
def setup_test_env(tmp_path):
    """Set up test environment with config file."""
    # Create test config file
    config_file = tmp_path / "config.yml"
    with open(config_file, "w") as f:
        yaml.dump(TEST_CONFIG, f)

    # Store original environment
    original_env = {}
    for key in list(os.environ.keys()):
        if key.startswith("R4DAR_") or key == "DATABASE_URL":
            original_env[key] = os.environ[key]
            del os.environ[key]

    # Set test environment
    os.environ["R4DAR_CONFIG"] = str(config_file)
    os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test_db"

    # Set test mode
    Config.set_test_mode(True)

    yield

    # Restore original environment
    for key in list(os.environ.keys()):
        if key.startswith("R4DAR_") or key == "DATABASE_URL":
            del os.environ[key]
    for key, value in original_env.items():
        os.environ[key] = value

    # Reset test mode
    Config.set_test_mode(False)


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

    # Create a patched Database class
    def mock_init(self):
        self._engine = mock_db._engine
        self._async_engine = mock_db._async_engine
        self._SessionLocal = mock_db._SessionLocal
        self._AsyncSessionLocal = mock_db._AsyncSessionLocal
        self.session = mock_db.session
        self.async_session = mock_db.async_session
        self.get_engine = mock_db.get_engine
        self.get_async_engine = mock_db.get_async_engine
        self.is_initialized = mock_db.is_initialized

    with patch("src.backend.database.Database.__init__", mock_init), patch("src.backend.database.db", mock_db):
        yield mock_db
