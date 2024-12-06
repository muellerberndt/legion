import pytest
from unittest.mock import Mock, patch
import os
import sys
from aiohttp import web

def pytest_configure(config):
    """Configure test environment"""
    # Add extensions directory to Python path for tests
    extensions_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "extensions")
    if extensions_dir not in sys.path:
        sys.path.append(os.path.dirname(extensions_dir))
        
    # Create test extensions directory if it doesn't exist
    test_extensions_dir = os.path.join(os.path.dirname(__file__), "extensions")
    os.makedirs(test_extensions_dir, exist_ok=True)

@pytest.fixture(autouse=True)
def mock_config():
    """Mock config for all tests"""
    with patch('src.config.config.Config') as mock:
        config = Mock()
        # Set default test values
        config.openai_api_key = "test-key"
        config.openai_model = "gpt-4"
        config.data_dir = "./test_data"
        config.database_url = "postgresql://test:test@localhost:5432/test_db"
        config.etherscan_api_key = "test-etherscan-key"
        
        # Mock get method with new config structure
        def get_side_effect(key, default=None):
            if key == 'block_explorers':
                return {
                    'etherscan': {'key': 'test-etherscan-key'},
                    'basescan': {'key': 'test-basescan-key'},
                    'arbiscan': {'key': 'test-arbiscan-key'},
                    'polygonscan': {'key': 'test-polygonscan-key'},
                    'bscscan': {'key': 'test-bscscan-key'}
                }
            elif key == 'llm':
                return {
                    'openai': {
                        'key': 'test-key',
                        'model': 'gpt-4'
                    }
                }
            return default
            
        config.get.side_effect = get_side_effect
        
        mock.return_value = config
        yield config