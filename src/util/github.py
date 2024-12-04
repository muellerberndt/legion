import os
import requests
import json

def fetch_github_file(url: str, target_path: str) -> None:
    """
    Fetch a single file from GitHub and store it locally.
    
    Args:
        url: GitHub URL of the format https://github.com/owner/repo/blob/branch/path/to/file
        target_path: Path where to store the file
    """
    # Convert web URL to raw content URL
    raw_url = url.replace('github.com', 'raw.githubusercontent.com').replace('/blob/', '/')
    
    # Fetch file content
    response = requests.get(raw_url)
    if response.status_code != 200:
        raise Exception(f"GitHub fetch error: Status code {response.status_code}")
    
    # Create target directory if it doesn't exist
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    
    # Write the content to the file
    with open(target_path, 'w') as f:
        f.write(response.text)

def fetch_github_repo(url: str, target_path: str) -> None:
    """
    Fetch an entire GitHub repository and store it locally.
    
    Args:
        url: GitHub repository URL of the format https://github.com/owner/repo
        target_path: Path where to store the repository files
    """
    # Extract owner and repo from URL
    parts = url.rstrip('/').split('/')
    owner = parts[-2]
    repo = parts[-1]
    
    # Construct API URL
    api_url = f"https://api.github.com/repos/{owner}/{repo}/zipball"
    
    # Fetch repository content
    response = requests.get(api_url)
    if response.status_code != 200:
        raise Exception(f"GitHub fetch error: Status code {response.status_code}")
    
    # Create target directory if it doesn't exist
    os.makedirs(target_path, exist_ok=True)
    
    # Save zip file temporarily
    zip_path = os.path.join(target_path, 'repo.zip')
    with open(zip_path, 'wb') as f:
        f.write(response.content)
    
    # Extract zip file
    import zipfile
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(target_path)
    
    # Remove temporary zip file
    os.remove(zip_path)