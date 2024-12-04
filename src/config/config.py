import yaml
import os
from typing import Dict, Any
from jsonschema import validate
from src.config.schema import CONFIG_SCHEMA

class Config:
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self.load_config()
    
    def load_config(self):
        """Load configuration from file."""
        config_path = os.getenv('R4DAR_CONFIG', 'config.yml')
        
        with open(config_path, 'r') as f:
            self._config = yaml.safe_load(f)
            
        # Validate against schema
        try:
            validate(instance=self._config, schema=CONFIG_SCHEMA)
        except Exception as e:
            raise ValueError(f"Invalid configuration: {str(e)}")
    
    @property
    def database_url(self) -> str:
        """Get database connection URL."""
        db = self._config['database']
        return f"postgresql://{db['user']}:{db['password']}@{db['host']}:{db['port']}/{db['name']}"
    
    @property
    def etherscan_api_key(self) -> str:
        """Get Etherscan API key."""
        return self._config.get('api', {}).get('etherscan', {}).get('key')
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        if '.' in key:
            # Handle nested keys
            keys = key.split('.')
            value = self._config
            for k in keys:
                if isinstance(value, dict):
                    value = value.get(k, default)
                else:
                    return default
            return value
        return self._config.get(key, default)
    
    @property
    def data_dir(self) -> str:
        """Get the data directory path"""
        return self._config.get('data_dir')
    
    @property
    def openai_api_key(self) -> str:
        """Get OpenAI API key"""
        key = self.get('api.openai.key')
        if not key:
            raise ValueError("OpenAI API key not configured")
        return key
    
    @property
    def openai_model(self) -> str:
        """Get OpenAI model to use"""
        return self.get('api.openai.model', 'gpt-4')