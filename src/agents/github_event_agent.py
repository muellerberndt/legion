from typing import Dict, Any, Optional, Tuple
from src.agents.base_agent import BaseAgent
from src.backend.database import DBSessionMixin
from src.models.base import Asset, Project
from sqlalchemy import or_


class GitHubSecurityAgent(BaseAgent, DBSessionMixin):
    """Agent specialized in analyzing GitHub events for security implications

    This agent:
    1. Analyzes PR and commit content for security relevance
    2. Links changes to known vulnerabilities and patterns
    3. Provides context from associated bounty programs
    4. Generates summaries focused on security implications
    """

    def __init__(self):
        # Add specialized prompt for security analysis
        custom_prompt = """You are specialized in analyzing GitHub pull requests and commits for security implications.

Your responsibilities:
1. Analyze code changes for potential security impacts
2. Identify patterns that match known vulnerability types
3. Link changes to relevant bounty program scope and rules
4. Generate clear, actionable summaries for security researchers

Focus areas:
- Smart contract vulnerabilities (reentrancy, access control, etc.)
- Protocol design issues
- Integration and dependency risks
- Gas optimization problems
- Potential economic attack vectors"""

        # Specify commands this agent can use
        command_names = []

        super().__init__(custom_prompt=custom_prompt, command_names=command_names)
        DBSessionMixin.__init__(self)

    def find_related_asset(self, repo_url: str) -> Optional[Tuple[Asset, Project]]:
        """Find an asset and its project related to the given repo URL"""
        try:
            with self.get_session() as session:
                # Clean up the URL for comparison
                repo_url = repo_url.rstrip("/")
                if repo_url.endswith(".git"):
                    repo_url = repo_url[:-4]

                # Query for assets with matching repo_url
                asset = (
                    session.query(Asset)
                    .filter(
                        or_(
                            Asset.source_url.like(f"{repo_url}%"),
                        )
                    )
                    .first()
                )

                if asset:
                    # Get the first associated project
                    project = session.query(Project).join(Project.assets).filter(Asset.id == asset.id).first()
                    return asset, project

                return None

        except Exception as e:
            self.logger.error(f"Error searching for related asset: {str(e)}")
            return None

    async def analyze_pr(self, repo_url: str, pr_data: Dict[str, Any]) -> str:
        """Analyze a pull request for security implications

        Args:
            repo_url: URL of the repository
            pr_data: Pull request data from GitHub

        Returns:
            Analysis summary
        """
        try:
            # Find related asset and project
            asset_info = self.find_related_asset(repo_url)

            # Build context for analysis
            context = [
                f"Analyzing PR #{pr_data.get('number')} in {repo_url}",
                f"Title: {pr_data.get('title')}",
                f"Description: {pr_data.get('body', 'No description')}",
                f"Changed files: {pr_data.get('changed_files', 0)}",
                f"Additions: {pr_data.get('additions', 0)}",
                f"Deletions: {pr_data.get('deletions', 0)}",
            ]

            if asset_info:
                asset, project = asset_info
                context.extend(
                    [
                        "\nProject Context:",
                        f"Project: {project.name}",
                        f"Type: {project.project_type}",
                        f"Description: {project.description}",
                    ]
                )

            # Get AI analysis
            analysis_prompt = "\n".join(
                [
                    "Analyze this pull request for security implications.",
                    "Consider:",
                    "1. What security-relevant changes are being made?",
                    "2. Are there any potential vulnerability patterns?",
                    "3. What specific areas should security researchers review?",
                    "4. How does this relate to known vulnerability types?",
                    "\nContext:",
                    "\n".join(context),
                ]
            )

            messages = [{"role": "user", "content": analysis_prompt}]
            analysis = await self.chat_completion(messages)

            return analysis

        except Exception as e:
            self.logger.error(f"Failed to analyze PR: {str(e)}")
            raise

    async def analyze_commit(self, repo_url: str, commit_data: Dict[str, Any]) -> str:
        """Analyze a commit for security implications

        Args:
            repo_url: URL of the repository
            commit_data: Commit data from GitHub

        Returns:
            Analysis summary
        """
        try:
            # Find related asset and project
            asset_info = self.find_related_asset(repo_url)

            # Build context for analysis
            context = [
                f"Analyzing commit in {repo_url}",
                f"Message: {commit_data.get('commit', {}).get('message', 'No message')}",
                f"Author: {commit_data.get('commit', {}).get('author', {}).get('name', 'Unknown')}",
            ]

            if asset_info:
                asset, project = asset_info
                context.extend(
                    [
                        "\nProject Context:",
                        f"Project: {project.name}",
                        f"Type: {project.project_type}",
                        f"Description: {project.description}",
                    ]
                )

            # Search for similar patterns
            similar_patterns = await self.execute_command(
                "semantic_search", query=f"Find security issues similar to: {commit_data.get('commit', {}).get('message')}"
            )

            # Get AI analysis
            analysis_prompt = "\n".join(
                [
                    "Analyze this commit for security implications.",
                    "Consider:",
                    "1. What security-relevant changes are being made?",
                    "2. Are there any potential vulnerability patterns?",
                    "3. What specific areas should security researchers review?",
                    "4. How does this relate to known vulnerability types?",
                    "\nContext:",
                    "\n".join(context),
                    "\nSimilar patterns found:",
                    similar_patterns,
                ]
            )

            messages = [{"role": "user", "content": analysis_prompt}]
            analysis = await self.chat_completion(messages)

            return analysis

        except Exception as e:
            self.logger.error(f"Failed to analyze commit: {str(e)}")
            raise
