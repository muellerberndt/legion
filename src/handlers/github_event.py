from src.handlers.base import Handler, HandlerTrigger, HandlerResult
from src.services.telegram import TelegramService
from src.util.logging import Logger
from src.backend.database import DBSessionMixin
from src.models.base import Asset, Project
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import or_
from src.ai.llm import chat_completion

# Security analysis prompt template
SECURITY_ANALYSIS_PROMPT = """You are a security researcher analyzing GitHub events. For each analysis:

1. Provide a single paragraph summarizing the change and its potential security relevance
2. On a new line, add "Security Impact: Yes" or "Security Impact: No"

Focus on smart contract security, access control, state modifications, and potential vulnerabilities.
Be concise and direct in your analysis."""


class GitHubEventHandler(Handler, DBSessionMixin):
    """Handler for GitHub events (PR and push)"""

    def __init__(self):
        Handler.__init__(self)
        DBSessionMixin.__init__(self)
        self.logger = Logger("GitHubEventHandler")
        self.logger.debug("GitHubEventHandler initialized")

    @classmethod
    def get_triggers(cls) -> List[HandlerTrigger]:
        """Get list of triggers this handler listens for"""
        triggers = [HandlerTrigger.GITHUB_PR, HandlerTrigger.GITHUB_PUSH]
        Logger("GitHubEventHandler").debug(f"Registering triggers: {[t.name for t in triggers]}")
        return triggers

    def find_related_asset(self, repo_url: str) -> Optional[Tuple[Asset, Project]]:
        """Find an asset and its project related to the given repo URL"""
        try:
            with self.get_session() as session:
                # Clean up the URL for comparison
                repo_url = repo_url.rstrip("/")
                if repo_url.endswith(".git"):
                    repo_url = repo_url[:-4]

                # Query for assets with matching repo_url or file_url
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

    async def analyze_pr(self, repo_url: str, pr_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a pull request for security implications"""
        pr_content = f"""
Repository: {repo_url}
Title: {pr_data.get('title')}
Description: {pr_data.get('body', 'No description')}
Changed Files: {pr_data.get('changed_files', 0)}
Additions: {pr_data.get('additions', 0)}
Deletions: {pr_data.get('deletions', 0)}
"""
        prompt = (
            "Analyze this pull request and provide a single sentence summary of the "
            "change and potential security impact, if any. Always end with "
            "'Security Impact: Yes' or 'Security Impact: No':"
        )

        response = await chat_completion(
            [{"role": "system", "content": SECURITY_ANALYSIS_PROMPT}, {"role": "user", "content": f"{prompt}\n{pr_content}"}]
        )

        return self.process_analysis(response)

    async def analyze_commit(self, repo_url: str, commit_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a commit for security implications"""
        commit_content = f"""
Repository: {repo_url}
Message: {commit_data.get('commit', {}).get('message', 'No message')}
Author: {commit_data.get('commit', {}).get('author', {}).get('name', 'Unknown')}
URL: {commit_data.get('html_url', '')}
"""
        prompt = (
            "Analyze this commit and provide a single sentence summary of the "
            "change and potential security impact, if any. Always end with "
            "'Security Impact: Yes' or 'Security Impact: No':"
        )

        response = await chat_completion(
            [
                {"role": "system", "content": SECURITY_ANALYSIS_PROMPT},
                {"role": "user", "content": f"{prompt}\n{commit_content}"},
            ]
        )

        return self.process_analysis(response)

    def process_analysis(self, response: str) -> Dict[str, Any]:
        """Process the LLM response and extract analysis and security impact"""
        try:
            # Split on newline to separate analysis from security impact
            parts = response.strip().split("\n")

            # If we have at least one line
            if len(parts) > 0:
                # If we have multiple lines, join all but the last
                if len(parts) > 1:
                    analysis = "\n".join(parts[:-1]).strip()
                    has_security_impact = "Security Impact: Yes" in parts[-1]
                else:
                    # Single line response - need to remove the "Security Impact" part
                    text = parts[0]
                    has_security_impact = "Security Impact: Yes" in text

                    # Remove the security impact text
                    if "Security Impact: Yes" in text:
                        analysis = text.replace("Security Impact: Yes", "").strip()
                    elif "Security Impact: No" in text:
                        analysis = text.replace("Security Impact: No", "").strip()
                    else:
                        return {
                            "has_security_impact": False,
                            "analysis": "Error processing analysis: Missing security impact marker",
                        }

                # If we ended up with empty analysis after removing security impact
                if not analysis:
                    analysis = "No analysis provided"

                return {"has_security_impact": has_security_impact, "analysis": analysis}

            # Empty response
            return {"has_security_impact": False, "analysis": "Error processing analysis: Empty response"}

        except Exception as e:
            return {"has_security_impact": False, "analysis": f"Error processing analysis: {str(e)}"}

    async def handle(self) -> HandlerResult:
        """Handle a GitHub event"""
        try:
            if not self.context:
                self.logger.error("No context provided")
                return HandlerResult(success=False, data={"error": "No context provided"})

            payload = self.context.get("payload")
            self.logger.debug(f"Payload: {payload}")

            if not payload:
                self.logger.error("No payload in context")
                return HandlerResult(success=False, data={"error": "No payload in context"})

            repo_url = payload.get("repo_url", "")

            # Process based on trigger type
            if self.trigger == HandlerTrigger.GITHUB_PR:
                pr_data = payload.get("pull_request", {})
                analysis_result = await self.analyze_pr(repo_url, pr_data)
                if not analysis_result.get("has_security_impact", False):
                    return HandlerResult(success=True, data={"message": "No security impact detected"})

                summary_lines = [
                    f"🔍 New PR with Security Impact in {repo_url}\n",
                    f"Title: {pr_data.get('title')}",
                    f"URL: {pr_data.get('html_url')}\n",
                    analysis_result.get("analysis", "No analysis available"),
                ]

            elif self.trigger == HandlerTrigger.GITHUB_PUSH:
                commit_data = payload.get("commit", {})
                analysis_result = await self.analyze_commit(repo_url, commit_data)
                if not analysis_result.get("has_security_impact", False):
                    return HandlerResult(success=True, data={"message": "No security impact detected"})

                summary_lines = [
                    f"📦 New commit with Security Impact in {repo_url}\n",
                    f"Message: {commit_data.get('commit', {}).get('message', 'No message')}",
                    f"URL: {commit_data.get('html_url', '')}\n",
                    analysis_result.get("analysis", "No analysis available"),
                ]

            else:
                return HandlerResult(success=False, data={"error": f"Unsupported trigger: {self.trigger}"})

            # Look for related assets
            if repo_url:
                result = self.find_related_asset(repo_url)
                if result:
                    asset, project = result
                    summary_lines.extend(
                        [
                            "\n📁 Related Project:",
                            f"Project: {project.name}",
                            f"Type: {project.project_type}",
                            f"\nAsset: {asset.source_url}",
                        ]
                    )

            # Send notification
            summary = "\n".join(summary_lines)
            telegram = TelegramService.get_instance()
            await telegram.send_message(summary)

            return HandlerResult(success=True, data={"message": summary})

        except Exception as e:
            self.logger.error(f"Error handling GitHub event: {str(e)}")
            return HandlerResult(success=False, data={"error": str(e)})
