import os
import aiohttp
import aiofiles
from src.config.config import Config
from src.util.logging import Logger

logger = Logger("GitHubUtil")


async def get_headers():
    """Get headers for GitHub API requests.

    Returns:
        dict: Headers including auth token if configured
    """
    config = Config()
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "R4dar-Security-Bot"}

    # Add auth token if configured
    if github_config := config.get("github", {}):
        if api_token := github_config.get("api_token"):
            headers["Authorization"] = f"token {api_token}"

    return headers


async def fetch_github_file(url: str, target_path: str) -> None:
    """
    Fetch a single file from GitHub and store it locally.

    Args:
        url: GitHub URL of the format https://github.com/owner/repo/blob/branch/path/to/file
        target_path: Path where to store the file
    """
    # Convert web URL to raw content URL
    raw_url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")

    # Fetch file content
    headers = await get_headers()
    async with aiohttp.ClientSession() as session:
        async with session.get(raw_url, headers=headers) as response:
            if response.status != 200:
                raise Exception(f"GitHub fetch error: Status code {response.status}")
            content = await response.text()

    # Create target directory if it doesn't exist
    os.makedirs(os.path.dirname(target_path), exist_ok=True)

    # Write the content to the file
    async with aiofiles.open(target_path, "w") as f:
        await f.write(content)


async def fetch_github_repo(url: str, target_path: str) -> None:
    """
    Fetch an entire GitHub repository and store it locally.

    Args:
        url: GitHub repository URL of the format https://github.com/owner/repo
        target_path: Path where to store the repository files
    """
    # Extract owner and repo from URL
    parts = url.rstrip("/").split("/")
    owner = parts[-2]
    repo = parts[-1]

    # Construct API URL
    api_url = f"https://api.github.com/repos/{owner}/{repo}/zipball"

    # Fetch repository content
    headers = await get_headers()
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url, headers=headers) as response:
            if response.status != 200:
                raise Exception(f"GitHub fetch error: Status code {response.status}")
            content = await response.read()

            # Check rate limit info
            rate_limit = response.headers.get("X-RateLimit-Remaining")
            if rate_limit:
                logger.info(f"GitHub API requests remaining: {rate_limit}")

    # Create target directory if it doesn't exist
    os.makedirs(target_path, exist_ok=True)

    # Save zip file temporarily
    zip_path = os.path.join(target_path, "repo.zip")
    with open(zip_path, "wb") as f:
        f.write(content)

    # Extract zip file
    import zipfile

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(target_path)

    # Remove temporary zip file
    os.remove(zip_path)


async def check_rate_limit() -> dict:
    """Check current GitHub API rate limit status.

    Returns:
        dict: Rate limit information including remaining requests
    """
    headers = await get_headers()
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.github.com/rate_limit", headers=headers) as response:
            if response.status != 200:
                raise Exception(f"Failed to check rate limit: {response.status}")
            return await response.json()
