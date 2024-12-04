import pytest
from unittest.mock import Mock, patch

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
        
        # Mock get method
        config.get.return_value = {}
        
        mock.return_value = config
        yield config 