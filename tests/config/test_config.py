import pytest
from unittest.mock import patch, mock_open
from src.config.config import Config
import yaml
import os


@pytest.fixture(autouse=True)
def reset_config():
    """Reset Config singleton between tests"""
    Config._instance = None
    Config._config = None
    # Clear environment variables
    for key in list(os.environ.keys()):
        if key.startswith("R4DAR_"):
            del os.environ[key]
    yield


@pytest.fixture
def test_config_data():
    """Base test configuration"""
    return {
        "data_dir": "./test_data",
        "database": {
            "host": "localhost",
            "port": 5432,
            "name": "r4dar_test_db",
            "user": "r4dar_test",
            "password": "test_password",
        },
        "block_explorers": {
            "etherscan": {"key": "TEST_API_KEY"},
            "basescan": {"key": "TEST_BASESCAN_KEY"},
            "arbiscan": {"key": "TEST_ARBISCAN_KEY"},
            "polygonscan": {"key": "TEST_POLYGONSCAN_KEY"},
            "bscscan": {"key": "TEST_BSCSCAN_KEY"},
        },
        "llm": {"openai": {"key": "test-key", "model": "gpt-4"}},
        "telegram": {"bot_token": "test-bot-token", "chat_id": "test-chat-id"},
    }


def test_config_loading(test_config_data):
    """Test loading configuration from file"""
    with patch("builtins.open", mock_open(read_data=yaml.dump(test_config_data))):
        config = Config()
        assert config.data_dir == "./test_data"
        assert config.database_url == "postgresql://r4dar_test:test_password@localhost:5432/r4dar_test_db"
        assert config.openai_api_key == "test-key"
        assert config.openai_model == "gpt-4"


def test_environment_override(test_config_data):
    """Test environment variables overriding file config"""
    with patch("builtins.open", mock_open(read_data=yaml.dump(test_config_data))):
        with patch.dict(
            os.environ,
            {
                "R4DAR_DATA_DIR": "/prod/data",
                "R4DAR_BOT_TOKEN": "prod-bot-token",
                "R4DAR_CHAT_ID": "prod-chat-id",
                "R4DAR_DB_HOST": "prod-db-host",
                "R4DAR_OPENAI_KEY": "prod-openai-key",
            },
        ):
            config = Config()
            assert config.data_dir == "/prod/data"
            assert config.get("telegram.bot_token") == "prod-bot-token"
            assert config.get("telegram.chat_id") == "prod-chat-id"
            assert config.get("database.host") == "prod-db-host"
            assert config.openai_api_key == "prod-openai-key"


def test_nested_config_access():
    """Test accessing nested configuration values"""
    test_data = {"level1": {"level2": {"level3": "value"}}}
    with patch("builtins.open", mock_open(read_data=yaml.dump(test_data))):
        config = Config()
        assert config.get("level1.level2.level3") == "value"
        assert config.get("nonexistent.key") is None
        assert config.get("level1.nonexistent") is None


def test_default_values():
    """Test default values for missing configuration"""
    empty_config = {}
    with patch("builtins.open", mock_open(read_data=yaml.dump(empty_config))):
        config = Config()
        assert config.data_dir == "./data"  # Default value
        assert config.openai_model == "gpt-4"  # Default value
        assert config.database_url is None  # No default, returns None
        assert config.get("nonexistent", "default") == "default"


def test_partial_database_config():
    """Test handling of partial database configuration"""
    test_data = {
        "database": {
            "host": "localhost",
            # Missing other required fields
        }
    }
    with patch("builtins.open", mock_open(read_data=yaml.dump(test_data))):
        config = Config()
        assert config.database_url is None  # Should return None if any required field is missing


def test_environment_only_config():
    """Test configuration using only environment variables"""
    empty_config = {}
    with patch("builtins.open", mock_open(read_data=yaml.dump(empty_config))):
        with patch.dict(
            os.environ,
            {
                "R4DAR_DATA_DIR": "/env/data",
                "R4DAR_DB_HOST": "env-db-host",
                "R4DAR_DB_PORT": "5432",
                "R4DAR_DB_NAME": "env_db",
                "R4DAR_DB_USER": "env_user",
                "R4DAR_DB_PASSWORD": "env_pass",
            },
        ):
            config = Config()
            assert config.data_dir == "/env/data"
            assert "env-db-host" in config.database_url
            assert "env_db" in config.database_url
