import json
import os
import pytest
from unittest.mock import patch, Mock
from src.util.etherscan import fetch_verified_sources, ExplorerType


@pytest.fixture
def mock_config():
    config = Mock()
    config.etherscan_api_key = "dummy_api_key"
    return config


@pytest.fixture
def mock_response():
    return {
        "status": "1",
        "message": "OK",
        "result": [
            {
                "SourceCode": json.dumps(
                    {
                        "sources": {
                            "BeaconProxy.sol": {"content": "// SPDX-License-Identifier: MIT\ncontract BeaconProxy {}"},
                            "IBeacon.sol": {"content": "// SPDX-License-Identifier: MIT\ncontract IBeacon {}"},
                            "Proxy.sol": {"content": "// SPDX-License-Identifier: MIT\ncontract Proxy {}"},
                            "ERC1967Utils.sol": {"content": "// SPDX-License-Identifier: MIT\ncontract ERC1967Utils {}"},
                            "Address.sol": {"content": "// SPDX-License-Identifier: MIT\ncontract Address {}"},
                            "StorageSlot.sol": {"content": "// SPDX-License-Identifier: MIT\ncontract StorageSlot {}"},
                        }
                    }
                ),
                "ABI": "[]",
                "ContractName": "BeaconProxy",
                "CompilerVersion": "v0.8.0",
                "OptimizationUsed": "1",
                "Runs": "200",
                "ConstructorArguments": "",
                "EVMVersion": "default",
                "Library": "",
                "LicenseType": "MIT",
                "Proxy": "0",
                "Implementation": "",
                "SwarmSource": "",
            }
        ],
    }


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
    with patch("src.util.etherscan.Config", return_value=mock_config):
        # Mock the EVMExplorer
        mock_explorer = Mock()
        mock_explorer.is_supported_explorer.return_value = (True, ExplorerType.ETHERSCAN)
        mock_explorer.get_api_key.return_value = "dummy_key"
        mock_explorer.get_api_url.return_value = "https://api.etherscan.io/api"
        mock_explorer.logger = Mock()

        with patch("src.util.etherscan.EVMExplorer", return_value=mock_explorer):
            # Mock the aiohttp.ClientSession
            with patch("aiohttp.ClientSession", return_value=MockClientSession(mock_response)):
                # Test URL and target path
                etherscan_url = "https://etherscan.io/address/0x1234567890123456789012345678901234567890"
                target_path = str(tmp_path / "sources")

                # Call the function
                result = await fetch_verified_sources(etherscan_url, target_path)

                # Verify the function returned True
                assert result is True, "fetch_verified_sources should return True on success"

                # Debug: Print the contents of the target directory
                print(f"\nTarget directory contents: {os.listdir(target_path)}")

                # Verify the expected files were created (using basenames)
                expected_files = [
                    "BeaconProxy.sol",
                    "IBeacon.sol",
                    "Proxy.sol",
                    "ERC1967Utils.sol",
                    "Address.sol",
                    "StorageSlot.sol",
                ]

                for file_path in expected_files:
                    full_path = os.path.join(target_path, file_path)
                    assert os.path.exists(full_path), f"Expected file {file_path} not found"

                # Verify file contents (optional)
                with open(os.path.join(target_path, "BeaconProxy.sol")) as f:
                    content = f.read()
                    assert "BeaconProxy" in content, "File content verification failed"


@pytest.mark.asyncio
async def test_path_traversal_prevention(tmp_path, mock_config):
    """Test that path traversal attempts are blocked"""

    malicious_path = "foo/../../etc/passwd"

    # Modify mock response to include malicious paths
    malicious_response = {
        "status": "1",
        "message": "OK",
        "result": [
            {
                "SourceCode": json.dumps(
                    {
                        "sources": {
                            malicious_path: {"content": "malicious content"},
                        }
                    }
                ),
                "ABI": "[]",
                "ContractName": "Test",
            }
        ],
    }

    target_path = str(tmp_path / "sources")

    with patch("src.util.etherscan.Config", return_value=mock_config):
        mock_explorer = Mock()
        mock_explorer.is_supported_explorer.return_value = (True, ExplorerType.ETHERSCAN)
        mock_explorer.get_api_key.return_value = "dummy_key"
        mock_explorer.get_api_url.return_value = "https://api.etherscan.io/api"
        mock_explorer.logger = Mock()

        with patch("src.util.etherscan.EVMExplorer", return_value=mock_explorer):
            with patch("aiohttp.ClientSession", return_value=MockClientSession(malicious_response)):
                etherscan_url = "https://etherscan.io/address/0x1234567890123456789012345678901234567890"

                # Call the function
                result = await fetch_verified_sources(etherscan_url, target_path)

                # Function should return False when path traversal is detected
                assert result is False, "Function should return False when path traversal is detected"

                # Verify error was logged for path traversal
                mock_explorer.logger.error.assert_called_with(
                    f"Security error: Path traversal attempt detected for {malicious_path}"
                )

                # Verify no files were created
                assert not os.path.exists(os.path.join(target_path, malicious_path))
                assert len(os.listdir(target_path)) == 0, "No files should be created when path traversal is detected"
