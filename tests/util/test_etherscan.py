import json
import os
import pytest
from unittest.mock import patch, Mock
from src.util.etherscan import fetch_verified_sources
import aiohttp

@pytest.fixture
def mock_config():
    config = Mock()
    config.etherscan_api_key = "dummy_api_key"
    return config

@pytest.fixture
def mock_response():
    # Load the mock response data from the test file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    test_data_path = os.path.join(current_dir, '..', 'testdata', 'etherscan-verified-sources.json')

    with open(test_data_path, 'r') as f:
        mock_data = json.load(f)
        return mock_data

class MockResponse:
    def __init__(self, data):
        self._data = data
        
    async def json(self):
        return self._data
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

class MockClientSession:
    def __init__(self, response_data):
        self.response_data = response_data
        
    def get(self, url):
        return MockResponse(self.response_data)
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

@pytest.mark.asyncio
async def test_fetch_verified_sources(tmp_path, mock_config, mock_response):
    # Mock the Config class
    with patch('src.util.etherscan.Config', return_value=mock_config):
        # Mock the aiohttp.ClientSession
        with patch('aiohttp.ClientSession', return_value=MockClientSession(mock_response)):
            # Test URL and target path
            etherscan_url = "https://etherscan.io/address/0x1234567890123456789012345678901234567890"
            target_path = str(tmp_path / "sources")
            
            # Call the function
            await fetch_verified_sources(etherscan_url, target_path)
            
            # Verify the expected files were created
            expected_files = [
                "lib/openzeppelin-contracts/contracts/proxy/beacon/BeaconProxy.sol",
                "lib/openzeppelin-contracts/contracts/proxy/beacon/IBeacon.sol",
                "lib/openzeppelin-contracts/contracts/proxy/Proxy.sol",
                "lib/openzeppelin-contracts/contracts/proxy/ERC1967/ERC1967Utils.sol",
                "lib/openzeppelin-contracts/contracts/utils/Address.sol",
                "lib/openzeppelin-contracts/contracts/utils/StorageSlot.sol"
            ]
            
            for file_path in expected_files:
                full_path = os.path.join(target_path, file_path)
                assert os.path.exists(full_path), f"Expected file {file_path} not found"
                
                # Verify file contents are not empty
                with open(full_path, 'r') as f:
                    content = f.read()
                    assert content.strip(), f"File {file_path} is empty"
