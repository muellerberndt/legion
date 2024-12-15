from src.handlers.base import Handler, HandlerTrigger
from src.jobs.base import Job, JobStatus, JobResult
from src.jobs.manager import JobManager
from src.services.telegram import TelegramService
from src.util.logging import Logger
from src.backend.database import DBSessionMixin
from src.models.base import Asset, Project
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy import or_
from src.ai.llm import chat_completion

# Security analysis prompt template
SECURITY_ANALYSIS_PROMPT = """You are a security researcher analyzing GitHub events. For each analysis:

1. Provide a single paragraph summarizing the change and its potential security relevance
2. On a new line, add "Security Impact: Yes" or "Security Impact: No"

Focus on smart contract security, access control, state modifications, and potential vulnerabilities.
Be concise and direct in your analysis."""

async def analyze_pr(repo_url: str, pr_data: Dict[str, Any]) -> Dict[str, Any]:
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
    
    response = await chat_completion([
        {"role": "system", "content": SECURITY_ANALYSIS_PROMPT},
        {"role": "user", "content": f"{prompt}\n{pr_content}"}
    ])
    
    return process_analysis(response)

async def analyze_commit(repo_url: str, commit_data: Dict[str, Any]) -> Dict[str, Any]:
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
    
    response = await chat_completion([
        {"role": "system", "content": SECURITY_ANALYSIS_PROMPT},
        {"role": "user", "content": f"{prompt}\n{commit_content}"}
    ])
    
    return process_analysis(response)

def process_analysis(response: str) -> Dict[str, Any]:
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
                    # If no security impact marker is found, this is an error
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

class GitHubEventJob(Job, DBSessionMixin):
    """Job to process GitHub webhook payloads"""

    def __init__(self, event_type: str, payload: Dict[str, Any]):
        Job.__init__(self, "github_event")
        DBSessionMixin.__init__(self)
        self.event_type = event_type
        self.payload = payload
        self.logger = Logger("GitHubEventJob")

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

    async def process_pr(self) -> str:
        """Process a pull request event"""
        # Extract relevant information
        pr = self.payload.get("pull_request", {})
        repo_url = self.payload.get("repo_url", "")

        self.logger.debug(f"PROCESS PR: {repo_url} {pr}")

        # Get security analysis
        analysis_result = await analyze_pr(repo_url, pr)

        # Check if there's a security impact
        if not analysis_result.get("has_security_impact", False):
            self.logger.info("No security impact detected, skipping notification")
            return "No security impact detected"

        # Basic PR info
        summary_lines = [
            f"🔍 New PR with Security Impact in {repo_url}\n",
            f"Title: {pr.get('title')}",
            f"URL: {pr.get('html_url')}\n",
        ]

        # Add the analysis text
        analysis_text = analysis_result.get("analysis", "No analysis available")
        summary_lines.append(analysis_text)

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

        return "\n".join(summary_lines)

    async def process_push(self) -> str:
        """Process a push event"""
        repo_url = self.payload.get("repo_url", "")
        commit = self.payload.get("commit", {})

        self.logger.debug(f"PROCESS PUSH: {repo_url} {commit}")
        # Get security analysis
        analysis_result = await analyze_commit(repo_url, commit)

        # Check if there's a security impact
        if not analysis_result.get("has_security_impact", False):
            self.logger.info("No security impact detected, skipping notification")
            return "No security impact detected"

        # Basic push info
        summary_lines = [
            f"📦 New commit with Security Impact in {repo_url}\n",
            f"Message: {commit.get('commit', {}).get('message', 'No message')}",
            f"URL: {commit.get('html_url', '')}\n",
        ]

        # Add the analysis text
        analysis_text = analysis_result.get("analysis", "No analysis available")
        summary_lines.append(analysis_text)

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

        return "\n".join(summary_lines)

    async def start(self) -> None:
        """Process the GitHub event"""
        try:
            # Process based on event type
            if self.event_type == "pull_request":
                summary = await self.process_pr()
            elif self.event_type == "push":
                summary = await self.process_push()
            else:
                raise ValueError(f"Unsupported event type: {self.event_type}")

            self.result = JobResult(success=True, message=summary, data=self.payload)

            # Only send notification if there's a security impact (summary will indicate this)
            if "No security impact detected" not in summary:
                telegram = TelegramService.get_instance()
                await telegram.send_message(summary)

            self.status = JobStatus.COMPLETED
            self.completed_at = datetime.now(timezone.utc)

        except Exception as e:
            self.logger.error(f"Failed to process GitHub event: {str(e)}")
            self.status = JobStatus.FAILED
            self.error = str(e)
            raise

    async def stop_handler(self) -> None:
        """Stop the job"""
        if self.status == JobStatus.RUNNING:
            self.status = JobStatus.CANCELLED


class GitHubEventHandler(Handler):
    """Handler for GitHub events (PR and push)"""

    def __init__(self):
        super().__init__()
        self.logger = Logger("GitHubEventHandler")
        self.logger.debug("GitHubEventHandler initialized")

    @classmethod
    def get_triggers(cls) -> List[HandlerTrigger]:
        """Get list of triggers this handler listens for"""
        triggers = [HandlerTrigger.GITHUB_PR, HandlerTrigger.GITHUB_PUSH]
        Logger("GitHubEventHandler").debug(f"Registering triggers: {[t.name for t in triggers]}")
        return triggers

    async def handle(self) -> None:
        """Handle a GitHub event"""
        try:
            self.logger.debug("Starting handler")
            self.logger.debug(f"Trigger type: {type(self.trigger)}")
            self.logger.debug(f"Trigger value: {self.trigger}")
            self.logger.debug(f"Trigger dict: {self.trigger.__dict__}")

            if not self.context:
                self.logger.error("No context provided")
                return

            payload = self.context.get("payload")

            if not payload:
                self.logger.error("No payload in context")
                return

            # Determine event type from trigger
            if self.trigger == HandlerTrigger.GITHUB_PR:
                event_type = "pull_request"
            elif self.trigger == HandlerTrigger.GITHUB_PUSH:
                event_type = "push"
            else:
                self.logger.error(f"Unsupported trigger: {self.trigger}")
                return

            # Create and submit job
            job = GitHubEventJob(event_type, payload)

            job_manager = JobManager()

            await job_manager.submit_job(job)

        except Exception as e:
            self.logger.error(f"Error handling GitHub event: {str(e)}")
            raise
