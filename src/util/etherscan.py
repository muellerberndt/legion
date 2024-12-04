import os
import requests
import json
from src.config.config import Config

def fetch_verified_sources(etherscan_url: str, target_path: str) -> None:
    """
    Fetch verified sources from Etherscan and store them locally.
    
    Args:
        etherscan_url: URL of the format https://etherscan.io/address/{address}
        target_path: Path where to store the source files
    """
    # Extract address from URL and clean it
    address = etherscan_url.split('/')[-1].lower()
    # Remove any extra parts after the address (like #code)
    address = address.split('#')[0]
    
    # Get API key from config
    config = Config()
    api_key = config.etherscan_api_key
    
    if not api_key:
        raise ValueError("Etherscan API key not found in config")
    
    # Construct API URL
    api_url = f"https://api.etherscan.io/api?module=contract&action=getsourcecode&address={address}&apikey={api_key}"
    
    # Fetch source code
    response = requests.get(api_url)
    data = response.json()
    
    if data["status"] != "1":
        raise Exception(f"Etherscan API error: {data.get('message', 'Unknown error')}")
    
    # Create target directory if it doesn't exist
    os.makedirs(target_path, exist_ok=True)
        
    # Extract and store source files
    result = data["result"][0]
    source_code = result.get("SourceCode", "")
    
    if source_code:
        try:
            # Handle double-wrapped JSON (starts with {{ and ends with }})
            if source_code.startswith('{{') and source_code.endswith('}}'):
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
                with open(file_path, 'w') as f:
                    f.write(file_content)
                    
        except json.JSONDecodeError as e:
            # If not JSON, it might be a single file
            with open(os.path.join(target_path, f"{address}.sol"), 'w') as f:
                f.write(source_code)