import pytest
from unittest.mock import patch, mock_open
from src.config.config import Config
import yaml
import os


@pytest.fixture(autouse=True)
def reset_config():
    """Reset Config singleton between tests"""
    # Store original config path
    original_config = os.environ.get("R4DAR_CONFIG")

    # Reset singleton
    Config._instance = None
    Config._config = None

    # Clear environment variables
    for key in list(os.environ.keys()):
        if key.startswith("R4DAR_") or key == "DATABASE_URL":
            del os.environ[key]

    # Set config path to a non-existent file
    os.environ["R4DAR_CONFIG"] = "/tmp/nonexistent_config.yml"

    yield

    # Restore original config path
    if original_config:
        os.environ["R4DAR_CONFIG"] = original_config
    else:
        del os.environ["R4DAR_CONFIG"]


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


def test_environment_override(tmp_path):
    """Test that environment variables override file config"""
    config_data = {
        "data_dir": "./test_data",
        "database": {
            "host": "localhost",
            "port": 5432,
            "name": "test_db",
            "user": "test_user",
            "password": "test_pass",
        },
    }

    # Create test config file
    config_path = tmp_path / "config.yml"
    with open(config_path, "w") as f:
        yaml.dump(config_data, f)

    # Set environment variables
    with patch.dict(
        os.environ,
        {
            "R4DAR_CONFIG": str(config_path),
            "R4DAR_DATA_DIR": "/prod/data",
            "DATABASE_URL": "postgresql://prod_user:prod_pass@prod-host:5432/prod_db",
        },
    ):
        # Reset singleton
        Config._instance = None
        Config._config = None

        config = Config()
        assert config.get("data_dir") == "/prod/data"
        assert config.get("database.url") == "postgresql://prod_user:prod_pass@prod-host:5432/prod_db"


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
    with patch.dict(
        os.environ,
        {
            "R4DAR_DATA_DIR": "/env/data",
            "DATABASE_URL": "postgresql://env_user:env_pass@env-host:5432/env_db",
        },
    ):
        # Reset singleton
        Config._instance = None
        Config._config = None

        config = Config()
        assert config.get("data_dir") == "/env/data"
        assert config.get("database.url") == "postgresql://env_user:env_pass@env-host:5432/env_db"


@pytest.fixture(autouse=True)
def mock_config_path(monkeypatch, tmp_path):
    """Mock config path for all tests"""
    config_file = tmp_path / "config.yml"
    monkeypatch.setenv("R4DAR_CONFIG", str(config_file))
    # Reset Config singleton between tests
    Config._instance = None
    Config._config = None
    # Create empty config file
    with open(config_file, "w") as f:
        yaml.dump({}, f)  # Empty but valid YAML
    return config_file


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up environment variables for testing"""
    # First clear all block explorer variables
    for explorer in ["ETHERSCAN", "BASESCAN", "ARBISCAN", "POLYGONSCAN", "BSCSCAN"]:
        var_name = f"R4DAR_{explorer}_KEY"
        print(f"Clearing {var_name}: current value = {os.environ.get(var_name)}")
        monkeypatch.delenv(var_name, raising=False)

    # Set only the ones we want to test
    env_vars = {
        "R4DAR_ETHERSCAN_KEY": "test_etherscan_key",
        "R4DAR_BASESCAN_KEY": "test_basescan_key",
        "R4DAR_ARBISCAN_KEY": "test_arbiscan_key",
        "R4DAR_BOT_TOKEN": "test_bot_token",
        "R4DAR_CHAT_ID": "test_chat_id",
        "R4DAR_OPENAI_KEY": "test_openai_key",
        "DATABASE_URL": "postgresql://user:pass@host:5432/db",
        "R4DAR_DATA_DIR": "/test/data",
    }

    # Set new values
    for key, value in env_vars.items():
        print(f"Setting {key} = {value}")
        monkeypatch.setenv(key, value)

    # Verify final state
    print("\nFinal environment state:")
    for explorer in ["ETHERSCAN", "BASESCAN", "ARBISCAN", "POLYGONSCAN", "BSCSCAN"]:
        var_name = f"R4DAR_{explorer}_KEY"
        print(f"{var_name}: {os.environ.get(var_name)}")

    return env_vars


@pytest.fixture
def clean_env_vars(monkeypatch):
    """Fixture for tests that need a clean environment without any block explorer keys"""
    # Clear all block explorer environment variables
    for explorer in ["ETHERSCAN", "BASESCAN", "ARBISCAN", "POLYGONSCAN", "BSCSCAN"]:
        var_name = f"R4DAR_{explorer}_KEY"
        print(f"Clearing {var_name}: current value = {os.environ.get(var_name)}")
        monkeypatch.delenv(var_name, raising=False)

    # Verify environment is clean
    for explorer in ["ETHERSCAN", "BASESCAN", "ARBISCAN", "POLYGONSCAN", "BSCSCAN"]:
        var_name = f"R4DAR_{explorer}_KEY"
        print(f"After clearing {var_name}: value = {os.environ.get(var_name)}")
    return {}


def test_load_config_from_env_no_file(mock_env_vars, mock_config_path):
    """Test loading config from environment when no config file exists"""
    config = Config()

    # Verify block explorers were loaded from env
    block_explorers = config.get("block_explorers", {})
    assert block_explorers is not None
    assert block_explorers["etherscan"]["key"] == "test_etherscan_key"
    assert block_explorers["basescan"]["key"] == "test_basescan_key"
    assert block_explorers["arbiscan"]["key"] == "test_arbiscan_key"

    # Verify other config was loaded
    assert config.get("telegram.bot_token") == "test_bot_token"
    assert config.get("telegram.chat_id") == "test_chat_id"
    assert config.get("llm.openai.key") == "test_openai_key"
    assert config.get("database.url") == "postgresql://user:pass@host:5432/db"


def test_load_config_empty_block_explorers(mock_env_vars, mock_config_path):
    """Test loading config with empty block_explorers section"""
    with open(mock_config_path, "w") as f:
        f.write("block_explorers: {}")

    config = Config()

    block_explorers = config.get("block_explorers", {})
    assert block_explorers is not None
    assert block_explorers["etherscan"]["key"] == "test_etherscan_key"
    assert block_explorers["basescan"]["key"] == "test_basescan_key"
    assert block_explorers["arbiscan"]["key"] == "test_arbiscan_key"


def test_load_config_missing_block_explorers(mock_env_vars, mock_config_path):
    """Test loading config with missing block_explorers section"""
    with open(mock_config_path, "w") as f:
        f.write("some_other_config: value")

    config = Config()

    block_explorers = config.get("block_explorers", {})
    assert block_explorers is not None
    assert block_explorers["etherscan"]["key"] == "test_etherscan_key"
    assert block_explorers["basescan"]["key"] == "test_basescan_key"
    assert block_explorers["arbiscan"]["key"] == "test_arbiscan_key"


def test_block_explorer_structure(clean_env_vars, mock_config_path):
    """Test that block_explorers structure is properly initialized"""
    # Print all environment variables for debugging
    print("\nEnvironment variables at start of test:")
    for key, value in os.environ.items():
        if "KEY" in key:
            print(f"{key}: {value}")

    config = Config()

    # Verify block_explorers exists and has proper structure
    block_explorers = config.get("block_explorers")
    print("\nBlock explorer config:")
    for explorer, data in block_explorers.items():
        print(f"{explorer}: {data}")

    assert isinstance(block_explorers, dict)

    # Check each explorer has proper structure
    expected_explorers = ["etherscan", "basescan", "arbiscan", "polygonscan", "bscscan"]
    for explorer in expected_explorers:
        assert explorer in block_explorers, f"Missing explorer: {explorer}"
        assert isinstance(block_explorers[explorer], dict), f"Explorer {explorer} is not a dict"
        assert "key" in block_explorers[explorer], f"Explorer {explorer} missing 'key' field"
        assert block_explorers[explorer]["key"] is None, f"Explorer {explorer} key should be None by default"


def test_block_explorer_env_override(mock_env_vars, mock_config_path):
    """Test that environment variables properly override block explorer keys"""
    # Create config file with empty block_explorers
    with open(mock_config_path, "w") as f:
        f.write(
            """
block_explorers:
  etherscan:
    key: null
  basescan:
    key: null
  arbiscan:
    key: null
"""
        )

    config = Config()

    # Verify block explorers were loaded from env
    block_explorers = config.get("block_explorers")
    assert isinstance(block_explorers, dict)

    # Check specific values from environment
    assert block_explorers["etherscan"]["key"] == "test_etherscan_key"
    assert block_explorers["basescan"]["key"] == "test_basescan_key"
    assert block_explorers["arbiscan"]["key"] == "test_arbiscan_key"

    # Check other explorers have null keys
    assert block_explorers["polygonscan"]["key"] is None
    assert block_explorers["bscscan"]["key"] is None


def test_block_explorer_partial_config(mock_env_vars, mock_config_path):
    """Test loading config with partial block_explorers section"""
    # Create config with only some explorers
    with open(mock_config_path, "w") as f:
        f.write(
            """
block_explorers:
  etherscan:
    key: file_key
"""
        )

    config = Config()

    # Verify structure
    block_explorers = config.get("block_explorers")
    assert isinstance(block_explorers, dict)

    # Environment should override file
    assert block_explorers["etherscan"]["key"] == "test_etherscan_key"

    # Other explorers should exist with proper structure
    assert block_explorers["basescan"]["key"] == "test_basescan_key"
    assert block_explorers["arbiscan"]["key"] == "test_arbiscan_key"
    assert block_explorers["polygonscan"]["key"] is None
    assert block_explorers["bscscan"]["key"] is None
