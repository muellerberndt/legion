import os
import aiohttp
import json
import aiofiles
from src.config.config import Config
from typing import Optional, Tuple
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
        self.logger = logging.getLogger("EVMExplorer")

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
                    self.logger.info(f"Checking API key for {config_key}: {'present' if api_key else 'missing'}")
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
        self.logger.info(f"Getting API key for {config_key} from path {config_path}: {'present' if api_key else 'missing'}")
        return api_key if api_key else None


async def fetch_verified_sources(explorer_url: str, target_path: str) -> None:
    """
    Fetch verified sources from an EVM explorer and store them locally.

    Args:
        explorer_url: URL of the format https://{explorer_domain}/address/{address}
        target_path: Path where to store the source files
    """
    # Check if this is a supported explorer
    explorer = EVMExplorer()
    is_supported, explorer_type = explorer.is_supported_explorer(explorer_url)

    if not is_supported:
        if explorer_type:
            raise ValueError(f"No API key configured for {explorer_type.value}")
        else:
            raise ValueError("Unsupported explorer URL")

    # Extract address from URL and clean it
    address = explorer_url.split("/")[-1].lower()
    # Remove any extra parts after the address (like #code)
    address = address.split("#")[0]

    # Get API key and URL
    api_key = explorer.get_api_key(explorer_type)
    api_url = explorer.get_api_url(explorer_type)

    # Construct API URL
    full_api_url = f"{api_url}?module=contract&action=getsourcecode&address={address}&apikey={api_key}"

    # Fetch source code
    async with aiohttp.ClientSession() as session:
        async with session.get(full_api_url) as response:
            data = await response.json()

    if data["status"] != "1":
        raise Exception(f"Explorer API error: {data.get('message', 'Unknown error')}")

    # Create target directory if it doesn't exist
    os.makedirs(target_path, exist_ok=True)

    # Extract and store source files
    result = data["result"][0]
    source_code = result.get("SourceCode", "")

    if source_code:
        try:
            # Handle double-wrapped JSON (starts with {{ and ends with }})
            if source_code.startswith("{{") and source_code.endswith("}}"):
                # Remove the double braces
                source_code = source_code[1:-1].strip()

            # Parse the JSON directly
            source_data = json.loads(source_code)

            # Extract all source files
            sources = source_data.get("sources", {})

            for filename, filedata in sources.items():
                file_content = filedata.get("content", "")

                # Create directories if they don't exist
                file_path = os.path.join(target_path, filename)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                # Write the content to the file
                async with aiofiles.open(file_path, "w") as f:
                    await f.write(file_content)

        except json.JSONDecodeError:
            # If not JSON, it might be a single file
            async with aiofiles.open(os.path.join(target_path, f"{address}.sol"), "w") as f:
                await f.write(source_code)
