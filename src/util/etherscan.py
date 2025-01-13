import os
import aiohttp
import json
import aiofiles
from src.config.config import Config
from typing import Optional, Tuple, List, Dict
from urllib.parse import urlparse
from enum import Enum


class ExplorerType(Enum):
    """Supported EVM explorer types"""

    ETHERSCAN = "etherscan"
    ARBISCAN = "arbiscan"
    POLYGONSCAN = "polygonscan"
    BASESCAN = "basescan"
    BSCSCAN = "bscscan"


class EVMExplorer:
    """Handles interaction with various EVM blockchain explorers"""

    # Explorer configurations
    EXPLORERS = {
        ExplorerType.ETHERSCAN: {
            "domain": "etherscan.io",
            "api_url": "https://api.etherscan.io/api",
            "config_key": "etherscan",
        },
        ExplorerType.ARBISCAN: {"domain": "arbiscan.io", "api_url": "https://api.arbiscan.io/api", "config_key": "arbiscan"},
        ExplorerType.POLYGONSCAN: {
            "domain": "polygonscan.com",
            "api_url": "https://api.polygonscan.com/api",
            "config_key": "polygonscan",
        },
        ExplorerType.BASESCAN: {"domain": "basescan.org", "api_url": "https://api.basescan.org/api", "config_key": "basescan"},
        ExplorerType.BSCSCAN: {"domain": "bscscan.com", "api_url": "https://api.bscscan.com/api", "config_key": "bscscan"},
    }

    def __init__(self):
        import logging

        self.config = Config()
        self.logger = logging.getLogger("EVMExplorer")  # pylint: disable=no-member

    def is_supported_explorer(self, url: str) -> Tuple[bool, Optional[ExplorerType]]:
        """Check if a URL is from a supported explorer

        Args:
            url: The URL to check

        Returns:
            Tuple of (is_supported, explorer_type)
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Remove www. prefix if present
            if domain.startswith("www."):
                domain = domain[4:]

            # Find matching explorer
            for explorer_type, config in self.EXPLORERS.items():
                if domain == config["domain"]:
                    # Check if API key is configured
                    config_key = config["config_key"]
                    api_key = self.config.get(f"block_explorers.{config_key}.key")
                    self.logger.debug(f"Checking API key for {config_key}: {'present' if api_key else 'missing'}")
                    if api_key:
                        return True, explorer_type
                    else:
                        return False, explorer_type

            return False, None

        except Exception as e:
            self.logger.error(f"Error checking explorer support: {str(e)}")
            return False, None

    def get_api_url(self, explorer_type: ExplorerType) -> str:
        """Get the API URL for an explorer type"""
        return self.EXPLORERS[explorer_type]["api_url"]

    def get_api_key(self, explorer_type: ExplorerType) -> Optional[str]:
        """Get the API key for an explorer type"""
        config_key = self.EXPLORERS[explorer_type]["config_key"]
        config_path = f"block_explorers.{config_key}.key"
        api_key = self.config.get(config_path)
        self.logger.debug(f"Getting API key for {config_key} from path {config_path}: {'present' if api_key else 'missing'}")
        return api_key if api_key else None

    async def get_proxy_upgrade_events(self, source_url: str) -> List[Dict]:
        """Get proxy implementation upgrade events for an address"""
        try:
            # Clean up URL first
            source_url = source_url.split("#")[0]
            self.logger.info(f"Getting proxy upgrade events for {source_url}")

            # Check if this is a supported explorer URL
            is_supported, explorer_type = self.is_supported_explorer(source_url)  # Pass the full URL
            if not is_supported:
                if explorer_type:
                    raise ValueError(f"No API key configured for {explorer_type.value}")
                else:
                    raise ValueError("Unsupported explorer URL")

            # Extract clean address after URL validation
            address = source_url.split("/")[-1].lower()
            # Remove any extra parts after the address (like #code)
            address = address.split("#")[0]

            # Get API key and URL
            api_key = self.get_api_key(explorer_type)
            api_url = self.get_api_url(explorer_type)

            # ERC1967 Upgrade event topic
            upgrade_topic = "0xbc7cd75a20ee27fd9adebab32041f755214dbc6bffa90cc0225b39da2e5c2d3b"

            # Construct API URL for getLogs
            full_api_url = (
                f"{api_url}?module=logs&action=getLogs" f"&address={address}" f"&topic0={upgrade_topic}" f"&apikey={api_key}"
            )

            # Fetch logs
            async with aiohttp.ClientSession() as session:
                async with session.get(full_api_url) as response:
                    data = await response.json()

            if data["status"] != "1":
                self.logger.warning(f"No upgrade events found for {address}: {data.get('message', 'Unknown error')}")
                return []

            # Process events
            events = []
            for log in data["result"]:
                # Extract implementation address from topics[1]
                impl_address = "0x" + log["topics"][1][-40:]

                # Get block timestamp
                block_number = int(log["blockNumber"], 16)
                timestamp = await self._get_block_timestamp(explorer_type, block_number, api_key)

                events.append(
                    {
                        "implementation": impl_address.lower(),
                        "blockNumber": block_number,
                        "timestamp": timestamp,
                        "transactionHash": log["transactionHash"],
                    }
                )

            return sorted(events, key=lambda x: x["blockNumber"])

        except Exception as e:
            self.logger.error(f"Error getting proxy upgrade events: {str(e)}")
            return []

    async def _get_block_timestamp(self, explorer_type: ExplorerType, block_number: int, api_key: str) -> str:
        """Get timestamp for a block number"""
        try:
            api_url = self.get_api_url(explorer_type)
            full_api_url = f"{api_url}?module=block&action=getblockreward" f"&blockno={block_number}" f"&apikey={api_key}"

            async with aiohttp.ClientSession() as session:
                async with session.get(full_api_url) as response:
                    data = await response.json()

            if data["status"] == "1" and "result" in data:
                return data["result"]["timeStamp"]
            return None

        except Exception as e:
            self.logger.error(f"Error getting block timestamp: {str(e)}")
            return None


async def fetch_verified_sources(explorer_url: str, target_path: str) -> bool:
    """
    Fetch verified sources from an EVM explorer and store them locally.
    """

    explorer = EVMExplorer()
    try:
        # Clean URL by removing query parameters and #code suffix
        clean_url = explorer_url.split("?")[0].split("#")[0]
        explorer.logger.debug(f"Clean URL: {clean_url}")

        # Extract address from URL and clean it
        address = clean_url.split("/")[-1].lower()
        explorer.logger.debug(f"Extracted address: {address}")

        # Get API key and URL
        is_supported, explorer_type = explorer.is_supported_explorer(clean_url)
        explorer.logger.debug(f"Explorer support check: supported={is_supported}, type={explorer_type}")

        if not is_supported:
            if explorer_type:
                explorer.logger.error(f"No API key configured for {explorer_type.value}")
                return False
            else:
                explorer.logger.error("Unsupported explorer URL")
                return False

        # Get API key and check it
        api_key = explorer.get_api_key(explorer_type)
        explorer.logger.debug(f"API key retrieval result: {'present' if api_key else 'missing'}")

        if not api_key:
            explorer.logger.error(f"No API key available for {explorer_type.value}")
            return False

        explorer.logger.debug("About to construct API URL")
        api_url = explorer.get_api_url(explorer_type)
        explorer.logger.debug(f"Got API URL: {api_url}")

        # Construct API URL (only after we know we have a valid API key)
        full_api_url = f"{api_url}?module=contract&action=getsourcecode&address={address}&apikey={api_key}"
        explorer.logger.debug("Full API URL constructed (not showing due to API key)")

        # Fetch source code
        explorer.logger.debug("About to fetch source code")
        async with aiohttp.ClientSession() as session:
            async with session.get(full_api_url) as response:
                data = await response.json()

        if data["status"] != "1":
            explorer.logger.error(f"Explorer API error: {data.get('message', 'Unknown error')} for {address}")
            return False

        # Create target directory if it doesn't exist
        os.makedirs(target_path, exist_ok=True)

        # Extract and store source files
        result = data["result"][0]
        source_code = result.get("SourceCode", "")

        if not source_code:
            explorer.logger.error(f"No source code found for {address}")
            return False

        try:
            # Handle double-wrapped JSON (starts with {{ and ends with }})
            if source_code.startswith("{{") and source_code.endswith("}}"):
                source_code = source_code[1:-1].strip()

            # Try to parse as JSON
            try:
                source_data = json.loads(source_code)
                sources = source_data.get("sources", {})

                for filename, filedata in sources.items():
                    file_content = filedata.get("content", "")
                    # Sanitize the path: remove any leading slashes or dots
                    safe_filename = filename.lstrip("./\\")
                    file_path = os.path.join(target_path, safe_filename)

                    # SECURITY CHECK: Ensure the final path is strictly within target_path
                    real_file_path = os.path.realpath(file_path)
                    real_target_path = os.path.realpath(target_path)
                    if not real_file_path.startswith(real_target_path):
                        explorer.logger.error(f"Security error: Path traversal attempt detected for {filename}")
                        return False

                    # Only proceed if security check passes
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    async with aiofiles.open(file_path, "w") as f:
                        await f.write(file_content)

            except json.JSONDecodeError:
                # If not JSON, save as single file
                file_path = os.path.join(target_path, f"{address}.sol")
                async with aiofiles.open(file_path, "w") as f:
                    await f.write(source_code)

            return True

        except Exception as e:
            explorer.logger.error(f"Error processing source code for {address}: {str(e)}")
            return False

    except Exception as e:
        explorer.logger.error(f"Error fetching verified sources for {explorer_url}: {str(e)}")
        return False
