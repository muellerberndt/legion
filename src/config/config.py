import os
import yaml
from typing import Dict, Any, Optional
import re


class Config:
    """Configuration singleton"""

    _instance = None
    _config = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if Config._config is None:
            self.load_config()

    def load_config(self) -> None:
        """Load configuration from file and environment"""
        # Load base config
        config_path = os.getenv("R4DAR_CONFIG", "config.yml")
        if not os.path.exists(config_path):
            config_path = "config.yml.example"

        try:
            with open(config_path, "r") as f:
                Config._config = yaml.safe_load(f) or {}
        except Exception:
            Config._config = {}

        # Ensure base structure exists
        if "llm" not in Config._config:
            Config._config["llm"] = {}
        if "openai" not in Config._config["llm"]:
            Config._config["llm"]["openai"] = {}

        # Handle Fly.io DATABASE_URL if present
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            # Parse DATABASE_URL into our config format
            # Format: postgres://user:pass@host:5432/dbname
            match = re.match(r"postgres://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)", database_url)
            if match:
                user, password, host, port, dbname = match.groups()
                Config._config["database"] = {
                    "host": host,
                    "port": int(port),
                    "name": dbname,
                    "user": user,
                    "password": password,
                }

        # Override with environment-specific values
        env_overrides = {
            "data_dir": os.getenv("R4DAR_DATA_DIR"),
            "telegram": {
                "bot_token": os.getenv("R4DAR_BOT_TOKEN"),
                "chat_id": os.getenv("R4DAR_CHAT_ID"),
            },
            "database": {
                "host": os.getenv("R4DAR_DB_HOST"),
                "port": os.getenv("R4DAR_DB_PORT"),
                "name": os.getenv("R4DAR_DB_NAME"),
                "user": os.getenv("R4DAR_DB_USER"),
                "password": os.getenv("R4DAR_DB_PASSWORD"),
            },
            "block_explorers": {
                "etherscan": {"key": os.getenv("R4DAR_ETHERSCAN_KEY")},
                "basescan": {"key": os.getenv("R4DAR_BASESCAN_KEY")},
                "arbiscan": {"key": os.getenv("R4DAR_ARBISCAN_KEY")},
                "polygonscan": {"key": os.getenv("R4DAR_POLYGONSCAN_KEY")},
                "bscscan": {"key": os.getenv("R4DAR_BSCSCAN_KEY")},
            },
            "llm": {
                "openai": {
                    "key": os.getenv("R4DAR_OPENAI_KEY"),
                    "model": os.getenv("R4DAR_OPENAI_MODEL"),
                }
            },
        }

        # Update config with non-None environment values
        self._deep_update(Config._config, env_overrides)

    def _deep_update(self, base: Dict, update: Dict) -> None:
        """Recursively update a dictionary with non-None values"""
        for key, value in update.items():
            if value is None:
                continue
            if isinstance(value, dict):
                if key not in base:
                    base[key] = {}
                if isinstance(base[key], dict):
                    self._deep_update(base[key], value)
            elif value is not None:  # Only update if value is not None
                base[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value"""
        if not Config._config:
            return default

        # Handle nested keys
        current = Config._config
        for part in key.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current

    @property
    def data_dir(self) -> str:
        return self.get("data_dir", "./data")

    @property
    def database_url(self) -> Optional[str]:
        # First check for Fly.io DATABASE_URL
        fly_url = os.getenv("DATABASE_URL")
        if fly_url:
            return fly_url

        # Fall back to constructed URL from config
        db = self.get("database", {})
        if all(key in db for key in ["host", "port", "name", "user", "password"]):
            return f"postgresql://{db['user']}:{db['password']}@{db['host']}:{db['port']}/{db['name']}"
        return None

    @property
    def openai_api_key(self) -> Optional[str]:
        return self.get("llm.openai.key")

    @property
    def openai_model(self) -> str:
        return self.get("llm.openai.model", "gpt-4")
