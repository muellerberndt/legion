# isort: skip_file
# flake8: noqa: E402, F401
import os
from unittest.mock import patch, Mock
import pytest
import yaml
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from src.config.config import Config, DEFAULT_CONFIG


@pytest.fixture(autouse=True)
def setup_test_config(tmp_path):
    """Set up test configuration."""
    config_file = tmp_path / "config.yml"
    with open(config_file, "w") as f:
        yaml.dump(DEFAULT_CONFIG, f)

    os.environ["R4DAR_CONFIG"] = str(config_file)
    Config.set_test_mode(True)

    yield

    Config.set_test_mode(False)
    if "R4DAR_CONFIG" in os.environ:
        del os.environ["R4DAR_CONFIG"]


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

    with patch("src.backend.database.Database.__init__", return_value=None), patch("src.backend.database.db", mock_db):
        yield mock_db
