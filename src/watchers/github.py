from typing import List, Dict, Any, Optional
from src.jobs.watcher import WatcherJob
from src.models.github import GitHubRepoState
from src.handlers.base import HandlerTrigger
from src.config.config import Config
from src.util.logging import Logger
from src.backend.database import DBSessionMixin
from src.handlers.registry import HandlerRegistry
import aiohttp
from sqlalchemy import text
from datetime import datetime, timedelta, timezone
import asyncio
from urllib.parse import urlparse


class GitHubWatcher(WatcherJob, DBSessionMixin):
    """Watcher that polls GitHub API for repository updates"""

    def __init__(self):
        # Get poll interval from config or use default (5 minutes)
        config = Config()
        github_config = config.get("github", {})
        interval = github_config.get("poll_interval", 3600)  # 1 hour default
        super().__init__("github", interval)
        DBSessionMixin.__init__(self)
        self.logger = Logger("GitHubWatcher")

        self.api_token = github_config.get("api_token")

        self.logger.info(f"Github API token configured: {bool(self.api_token)}")
        self.session = None
        self.handler_registry = HandlerRegistry()

        # Log configuration state
        self.logger.info(
            "GitHub watcher initialized with config:",
            extra_data={
                "has_token": bool(self.api_token),
                "interval": interval,
                "config": {k: "..." if k == "api_token" else v for k, v in github_config.items()},
            },
        )

    async def initialize(self) -> None:
        """Initialize the watcher"""
        # Set up API session with or without token
        headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "R4dar-Security-Bot"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
            self.logger.debug("GitHub API token configured")
        else:
            self.logger.warning("No GitHub API token configured - rate limits will be strict")

        self.session = aiohttp.ClientSession(headers=headers)
        self.logger.debug(
            "GitHub API session initialized",
            extra_data={"headers": {k: "..." if k == "Authorization" else v for k, v in headers.items()}},
        )

    async def cleanup(self) -> None:
        """Clean up resources"""
        if self.session:
            await self.session.close()

    async def check(self) -> List[Dict[str, Any]]:
        """Check for updates in GitHub repositories"""
        try:
            # Get all repos in scope
            repos = await self._get_repos_in_scope()
            if not repos:
                self.logger.info("No GitHub repositories found in scope")
                return []

            self.logger.info(f"Found {len(repos)} repositories to check")

            # Check each repo for updates
            for repo in repos:
                try:
                    await self._check_repo_updates(repo)
                except Exception as e:
                    self.logger.error(f"Failed to check repo {repo['repo_url']}: {str(e)}")
                    continue

            return []

        except Exception as e:
            self.logger.error(f"Failed to check GitHub updates: {str(e)}")
            return []

    async def _get_repos_in_scope(self) -> List[Dict[str, Any]]:
        """Get all GitHub repositories from bounty projects"""
        try:
            async with self.get_async_session() as session:
                # First, check if we have any bounty projects
                project_query = text("SELECT COUNT(*) FROM projects WHERE project_type = 'bounty'")
                project_count = await session.scalar(project_query)
                self.logger.info(f"Found {project_count} bounty projects")

                # Check direct GitHub repos first
                direct_repos_query = text(
                    """
                    SELECT DISTINCT a.source_url, a.asset_type
                    FROM assets a
                    JOIN project_assets pa ON a.id = pa.asset_id
                    JOIN projects p ON pa.project_id = p.id
                    WHERE p.project_type = 'bounty'
                    AND a.asset_type IN ('github_repo', 'github_file')
                    LIMIT 5
                """
                )
                direct_result = await session.execute(direct_repos_query)
                direct_rows = direct_result.all()
                self.logger.info(f"Sample assets: {[(row.source_url, row.asset_type) for row in direct_rows]}")

                # Now try the full query
                query = text(
                    """
                    WITH repo_urls AS (
                        -- Direct repo assets
                        SELECT DISTINCT a.source_url
                        FROM assets a
                        JOIN project_assets pa ON a.id = pa.asset_id
                        JOIN projects p ON pa.project_id = p.id
                        WHERE p.project_type = 'bounty'
                        AND a.asset_type = 'github_repo'

                        UNION

                        -- Extract repos from file URLs
                        SELECT DISTINCT regexp_replace(a.source_url, '/blob/.*$', '')
                        FROM assets a
                        JOIN project_assets pa ON a.id = pa.asset_id
                        JOIN projects p ON pa.project_id = p.id
                        WHERE p.project_type = 'bounty'
                        AND a.asset_type = 'github_file'
                    )
                    SELECT
                        r.source_url as repo_url,
                        s.last_commit_sha,
                        s.last_pr_number,
                        s.last_check
                    FROM repo_urls r
                    LEFT JOIN github_repo_state s ON r.source_url = s.repo_url
                """
                )

                result = await session.execute(query)
                rows = result.all()
                self.logger.info(f"Found {len(rows)} repositories to watch")

                # Log some sample URLs for debugging
                if rows:
                    sample_urls = [row.repo_url for row in rows[:5]]
                    self.logger.info(f"Sample repository URLs: {sample_urls}")

                return [
                    {
                        "repo_url": row.repo_url,
                        "last_commit_sha": row.last_commit_sha,
                        "last_pr_number": row.last_pr_number,
                        "last_check": row.last_check,
                    }
                    for row in rows
                ]

        except Exception as e:
            self.logger.error(f"Failed to get repos in scope: {str(e)}")
            return []

    async def _check_repo_updates(self, repo: Dict[str, Any]) -> None:
        """Check a single repository for updates"""
        repo_url = repo["repo_url"]
        owner, name = self._parse_repo_url(repo_url)
        if not owner or not name:
            self.logger.debug(f"Invalid repo URL: {repo_url}")
            return

        self.logger.info(f"Checking updates for {repo_url}")
        self.logger.debug(f"Current state: {repo}")

        # Use interval * 2 for the cutoff time
        cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=self.interval * 2)

        # Ensure cutoff time is timezone-aware
        if cutoff_time.tzinfo is None:
            cutoff_time = cutoff_time.replace(tzinfo=timezone.utc)

        # Check commits and PRs in parallel
        commits_task = self._get_new_commits(owner, name, cutoff_time)
        prs_task = self._get_updated_prs(owner, name, cutoff_time)

        try:
            commits, prs = await asyncio.gather(commits_task, prs_task)
        except Exception as e:
            self.logger.error(f"Failed to fetch updates for {repo_url}: {str(e)}")
            return

        # Process commit updates - GitHub returns newest commits first
        last_commit_sha = repo.get("last_commit_sha")
        newest_sha = None

        self.logger.debug(f"Processing commits with last_commit_sha: {last_commit_sha}")

        # Reverse commits to process oldest first
        for commit in reversed(commits):
            if newest_sha is None:
                newest_sha = commit["sha"]  # First commit is the newest
                self.logger.debug(f"Set newest_sha to: {newest_sha}")

            # Trigger event if this is a new commit
            if not last_commit_sha or commit["sha"] != last_commit_sha:
                self.logger.info(f"Found new commit: {commit['sha']}")
                await self.handler_registry.trigger_event(
                    HandlerTrigger.GITHUB_PUSH, {"payload": {"repo_url": repo_url, "commit": commit}}
                )

        # Process PR updates
        last_pr_number = repo.get("last_pr_number") or 0  # Default to 0 if None
        self.logger.debug(f"Processing PRs with last_pr_number: {last_pr_number}")

        for pr in prs:
            pr_number = pr.get("number")
            if pr_number is None:
                self.logger.warning(f"PR missing number field: {pr}")
                continue

            # Trigger event for new PRs
            if pr_number > last_pr_number:
                self.logger.info(f"Found new PR: {pr_number}")
                await self.handler_registry.trigger_event(
                    HandlerTrigger.GITHUB_PR, {"payload": {"repo_url": repo_url, "pull_request": pr}}
                )

                # Keep track of the highest PR number
                last_pr_number = max(last_pr_number, pr_number)

        # Update repo state if we have new data
        if newest_sha or last_pr_number > 0:
            self.logger.debug(f"Updating repo state with newest_sha: {newest_sha}, last_pr_number: {last_pr_number}")
            await self._update_repo_state(repo_url, newest_sha or repo.get("last_commit_sha"), last_pr_number)

    def _parse_repo_url(self, url: str) -> tuple[Optional[str], Optional[str]]:
        """Parse owner and repo name from GitHub URL"""
        try:
            parsed = urlparse(url)
            if parsed.netloc != "github.com":
                return None, None

            parts = parsed.path.strip("/").split("/")
            if len(parts) >= 2:
                return parts[0], parts[1]

        except Exception:
            pass

        return None, None

    async def _get_new_commits(self, owner: str, repo: str, since: datetime) -> List[Dict[str, Any]]:
        """Get new commits for a repository"""
        if not self.session:
            self.logger.warning("No session available for GitHub API calls")
            return []

        try:
            url = f"https://api.github.com/repos/{owner}/{repo}/commits"
            params = {"since": since.isoformat()}

            self.logger.debug(f"Fetching commits from {url}", extra_data={"params": params})
            response = await self.session.get(url, params=params)

            self.logger.debug(f"Commits API response status: {response.status}")
            if response.status == 200:
                data = await response.json() or []
                self.logger.debug(f"Found {len(data)} commits")
                return data
            elif response.status == 403:
                self.logger.warning("GitHub API rate limit exceeded or authentication required")
            elif response.status == 404:
                self.logger.warning(f"Repository not found: {owner}/{repo}")
            else:
                response_text = await response.text()
                self.logger.warning(f"Failed to get commits: HTTP {response.status}", extra_data={"response": response_text})
            return []
        except Exception as e:
            self.logger.error(f"Error fetching commits: {str(e)}")
            return []

    async def _get_updated_prs(self, owner: str, repo: str, since: datetime) -> List[Dict[str, Any]]:
        """Get updated pull requests for a repository"""
        if not self.session:
            self.logger.warning("No session available for GitHub API calls")
            return []

        try:
            url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
            params = {"state": "all", "sort": "updated", "direction": "desc"}

            self.logger.debug(f"Fetching PRs from {url}", extra_data={"params": params})
            response = await self.session.get(url, params=params)

            self.logger.debug(f"PRs API response status: {response.status}")
            if response.status == 200:
                prs = await response.json() or []
                self.logger.debug(f"Found {len(prs)} PRs before filtering")
                filtered_prs = [pr for pr in prs if datetime.fromisoformat(pr["updated_at"].replace("Z", "+00:00")) > since]
                self.logger.debug(f"Found {len(filtered_prs)} PRs after filtering by date")
                return filtered_prs
            elif response.status == 403:
                self.logger.warning("GitHub API rate limit exceeded or authentication required")
            elif response.status == 404:
                self.logger.warning(f"Repository not found: {owner}/{repo}")
            else:
                response_text = await response.text()
                self.logger.warning(f"Failed to get PRs: HTTP {response.status}", extra_data={"response": response_text})
            return []
        except Exception as e:
            self.logger.error(f"Error fetching PRs: {str(e)}")
            return []

    async def _update_repo_state(self, repo_url: str, commit_sha: str, pr_number: int) -> None:
        """Update repository state in database"""
        try:
            async with self.get_async_session() as session:
                state = await session.get(GitHubRepoState, repo_url)
                if not state:
                    state = GitHubRepoState(repo_url=repo_url)
                    session.add(state)

                state.last_commit_sha = commit_sha
                state.last_pr_number = pr_number
                state.last_check = datetime.utcnow()
                await session.commit()

        except Exception as e:
            self.logger.error(f"Failed to update repo state: {str(e)}")
