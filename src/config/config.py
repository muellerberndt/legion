import os
import json
import yaml
from typing import Any, Dict, List, Optional
from .schema import CONFIG_SCHEMA
import logging


def _get_nested_value(config: Dict[str, Any], path: str) -> Any:
    """Get a nested value from a dictionary using dot notation."""
    keys = path.split(".")
    value = config
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
        if value is None:
            return None
    return value


def _set_nested_value(config: Dict[str, Any], path: str, value: Any) -> None:
    """Set a nested value in a dictionary using dot notation."""
    keys = path.split(".")
    current = config
    for key in keys[:-1]:
        if not isinstance(current, dict):
            current = {}
        if key not in current:
            current[key] = {}
        current = current[key]
    if not isinstance(current, dict):
        current = {}
    current[keys[-1]] = value


def _convert_value(value: str, value_type: str) -> Any:
    """Convert string value to the specified type."""
    if value_type == "bool":
        return value.lower() in ("true", "1", "yes", "y")
    elif value_type == "int":
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    elif value_type == "list":
        if not value:
            return []
        return [item.strip() for item in value.split(",")]
    return value


def _get_schema_type(path: str) -> str:
    """Get the type of a field from the schema."""
    current = CONFIG_SCHEMA["properties"]
    for part in path.split("."):
        if part in current:
            if "type" in current[part]:
                schema_type = current[part]["type"]
                if schema_type == "integer":
                    return "int"
                elif schema_type == "boolean":
                    return "bool"
                elif schema_type == "array":
                    return "list"
                return "string"
            current = current[part].get("properties", {})
    return "string"


def load_config(config_path: str, test_mode: bool = False) -> Dict[str, Any]:
    """Load configuration from file and environment"""
    logger = logging.getLogger("Config")

    # Start with default config
    config = DEFAULT_CONFIG.copy()

    # Load from file if it exists
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            content = f.read()
            try:
                loaded = yaml.safe_load(content)
                if loaded is not None:
                    # Update nested dictionaries instead of replacing them
                    for key, value in loaded.items():
                        if isinstance(value, dict) and key in config and isinstance(config[key], dict):
                            config[key].update(value)
                        else:
                            config[key] = value
            except yaml.YAMLError:
                try:
                    loaded = json.loads(content)
                    # Update nested dictionaries instead of replacing them
                    for key, value in loaded.items():
                        if isinstance(value, dict) and key in config and isinstance(config[key], dict):
                            config[key].update(value)
                        else:
                            config[key] = value
                except json.JSONDecodeError as e:
                    raise ValueError(f"Failed to parse config file as YAML or JSON: {e}")

    # Load from environment variables
    logger.info("Loading environment variables...")
    for config_path, env_info in ENV_MAPPINGS.items():
        env_var = env_info if isinstance(env_info, str) else env_info["env"]
        env_type = env_info.get("type") if isinstance(env_info, dict) else None

        # Log the environment variable we're looking for
        value = os.environ.get(env_var)
        logger.info(f"Checking {env_var}: {'present' if value else 'missing'}")

        if value is not None:
            # Convert value based on type
            if env_type == "bool":
                value = value.lower() in ("true", "1", "yes", "on")
            elif env_type == "int":
                try:
                    value = int(value)
                except ValueError:
                    logger.warning(f"Failed to convert {env_var} value to int: {value}")
                    continue
            elif env_type == "list":
                value = [item.strip() for item in value.split(",") if item.strip()]

            # Update config at the specified path
            current = config
            *path_parts, final_key = config_path.split(".")

            # Ensure all parent paths exist
            for part in path_parts:
                if not isinstance(current, dict):
                    current = {}
                if part not in current:
                    current[part] = {}
                current = current[part]

            # Ensure the final container is a dictionary if needed
            if path_parts:  # Only if we're dealing with a nested path
                if not isinstance(current, dict):
                    current = {}

            current[final_key] = value

    # Ensure block_explorers structure is complete
    if "block_explorers" not in config:
        config["block_explorers"] = {}

    for explorer in ["etherscan", "basescan", "arbiscan", "polygonscan", "bscscan"]:
        if explorer not in config["block_explorers"]:
            config["block_explorers"][explorer] = {"key": None}
        elif not isinstance(config["block_explorers"][explorer], dict):
            config["block_explorers"][explorer] = {"key": None}
        elif "key" not in config["block_explorers"][explorer]:
            config["block_explorers"][explorer]["key"] = None

    # Log final block explorer configuration
    logger.info("Final block explorer configuration:")
    if isinstance(config.get("block_explorers"), dict):
        for explorer, data in config["block_explorers"].items():
            key_status = "present" if data.get("key") else "missing"
            logger.info(f"{explorer}: API key {key_status}")

    return config


class Config:
    """Configuration singleton"""

    _instance = None
    _config = None
    _test_mode = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance.initialize()
        return cls._instance

    def initialize(self):
        """Initialize the configuration"""
        if self._config is None:
            self.load_config()

    def load_config(self):
        """Load configuration from file and environment"""
        # Get config path from environment or use default
        config_path = os.environ.get("Legion_CONFIG", "config.yml")
        Config._config = load_config(config_path, test_mode=Config._test_mode)

    def load_extension_config(self, config_path: str) -> None:
        """Load extension-specific configuration and merge it with the main config"""
        if not os.path.exists(config_path):
            return

        with open(config_path, "r") as f:
            try:
                extension_config = yaml.safe_load(f)
                if extension_config and isinstance(extension_config, dict):
                    # Merge extension config with main config
                    for key, value in extension_config.items():
                        if isinstance(value, dict) and key in Config._config and isinstance(Config._config[key], dict):
                            Config._config[key].update(value)
                        else:
                            Config._config[key] = value
            except yaml.YAMLError as e:
                logging.getLogger("Config").error(f"Failed to load extension config {config_path}: {e}")

    @classmethod
    def set_test_mode(cls, enabled: bool = True):
        """Enable/disable test mode"""
        cls._test_mode = enabled
        # Reset config when changing test mode
        cls._config = None
        cls._instance = None

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value"""
        if not Config._config:
            return default
        value = _get_nested_value(Config._config, key)
        return value if value is not None else default

    @property
    def data_dir(self) -> str:
        return self.get("data_dir", "./data")

    @property
    def database_url(self) -> Optional[str]:
        """Get database URL from environment or config."""
        # Check for DATABASE_URL environment variable first
        db_url = os.environ.get("DATABASE_URL")
        if db_url:
            return db_url

        # Fall back to config-based URL
        db = self.get("database", {})
        if all(key in db for key in ["host", "port", "name", "user", "password"]):
            return f"postgresql://{db['user']}:{db['password']}@{db['host']}:{db['port']}/{db['name']}"

        return None

    @property
    def openai_api_key(self) -> Optional[str]:
        return self.get("llm.openai.key")

    @property
    def openai_model(self) -> str:
        return self.get("llm.openai.model")

    @property
    def llm_personality(self) -> str:
        return self.get("llm.personality")

    @property
    def watchers(self) -> List[str]:
        return self.get("watchers.active_watchers")


# Environment variable mappings
ENV_MAPPINGS = {
    # Core config
    "data_dir": "LEGION_DATA_DIR",
    "database.url": "DATABASE_URL",
    # Block explorer API keys
    "block_explorers.etherscan.key": "LEGION_ETHERSCAN_KEY",
    "block_explorers.basescan.key": "LEGION_BASESCAN_KEY",
    "block_explorers.arbiscan.key": "LEGION_ARBISCAN_KEY",
    # Telegram config
    "telegram.bot_token": "LEGION_BOT_TOKEN",
    "telegram.chat_id": "LEGION_CHAT_ID",
    # OpenAI config
    "llm.openai.key": "LEGION_OPENAI_KEY",
    "llm.openai.model": "LEGION_OPENAI_MODEL",
    "llm.personality": "Legion_LLM_PERSONALITY",
    # Other config
    "extensions_dir": "LEGION_EXTENSIONS_DIR",
    "active_extensions": {"env": "LEGION_EXTENSIONS", "type": "list"},
    "watchers.active_watchers": {"env": "LEGION_WATCHERS", "type": "list"},
    "github.api_token": "LEGION_GITHUB_TOKEN",
}

# Default configuration
DEFAULT_CONFIG = {
    "data_dir": "./data",
    "llm": {
        "openai": {"key": None, "model": "gpt-4o"},
        "personality": (
            "Research assistant of a web3 bug hunter, deeply embedded in web3 culture. "
            'Unironically use terms like "ser", "gm", "wagmi", "chad", "based", "banger". '
            "Often compliment the user on their elite security researcher status."
        ),
    },
    "watchers": {"active_watchers": []},
    "telegram": {"bot_token": None, "chat_id": None},
    "github": {},
    "extensions_dir": "./extensions",
    "active_extensions": [],
}
