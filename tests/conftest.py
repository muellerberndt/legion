# isort: skip_file
# flake8: noqa: E402
import pytest
from unittest.mock import patch, Mock, AsyncMock, MagicMock

# Set test mode before any imports
import os

os.environ["TEST_MODE"] = "1"

# Now import our modules
from src.config.config import Config
from src.backend.database import Database

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

# Create mock database
mock_db = Mock()
mock_db._engine = Mock()
mock_db._async_engine = Mock()
mock_db._SessionLocal = Mock()
mock_db._AsyncSessionLocal = Mock()
mock_db.session = Mock()
mock_db.async_session = Mock()
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

# Mock engine inspection results
mock_inspector = Mock()
mock_inspector.get_table_names.return_value = ["projects", "assets", "event_logs"]
mock_inspector.get_columns.return_value = [
    {"name": "id", "type": "INTEGER", "nullable": False},
    {"name": "name", "type": "VARCHAR", "nullable": True},
]
mock_inspector.get_pk_constraint.return_value = {"constrained_columns": ["id"]}
mock_inspector.get_foreign_keys.return_value = []

mock_engine = Mock()
mock_engine.connect.return_value = Mock()
mock_db.get_engine.return_value = mock_engine

# Apply patches
config_patcher = patch("src.config.config.load_config", return_value=TEST_CONFIG)
db_patcher = patch("src.backend.database.Database", return_value=mock_db)
db_instance_patcher = patch("src.backend.database.db", mock_db)
inspect_patcher = patch("sqlalchemy.inspect", return_value=mock_inspector)

# Start all patches
config_patcher.start()
db_patcher.start()
db_instance_patcher.start()
inspect_patcher.start()


@pytest.fixture(autouse=True)
def setup_test_env(request):
    """Setup test environment for each test"""
    # Reset singleton instances
    Config._instance = None
    Database._instance = None

    # For config tests, stop the config patch temporarily
    is_config_test = "tests/config/test_config.py" in str(request.node.fspath)
    if is_config_test:
        config_patcher.stop()

    yield

    # Cleanup
    Config._instance = None
    Database._instance = None

    # Restore config patch for non-config tests
    if is_config_test:
        config_patcher.start()


@pytest.fixture
def mock_database():
    """Mock database for testing"""
    mock_db = MagicMock()
    mock_session = AsyncMock()
    mock_session_context = AsyncMock()
    mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_context.__aexit__ = AsyncMock(return_value=None)
    mock_db.session = MagicMock(return_value=mock_session_context)

    # Make session async
    mock_session.add = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.delete = AsyncMock()
    mock_session.get = AsyncMock()
    mock_session.execute = AsyncMock()

    return mock_db


@pytest.fixture
def event_bus():
    """Mock event bus for testing"""
    from src.backend.event_bus import EventBus

    return EventBus()
