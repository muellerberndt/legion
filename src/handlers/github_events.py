from src.handlers.base import Handler, HandlerTrigger
from src.jobs.base import Job, JobType, JobStatus, JobResult
from src.jobs.manager import JobManager
from src.services.telegram import TelegramService
from src.util.logging import Logger
from src.backend.database import DBSessionMixin
from src.models.base import Asset, Project
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy import or_

class GitHubEventJob(Job, DBSessionMixin):
    """Job to process GitHub webhook payloads"""
    
    def __init__(self, event_type: str, payload: Dict[str, Any]):
        Job.__init__(self, JobType.AGENT)
        DBSessionMixin.__init__(self)
        self.event_type = event_type
        self.payload = payload
        self.logger = Logger("GitHubEventJob")
        
    def find_related_asset(self, repo_url: str) -> Optional[Tuple[Asset, Project]]:
        """Find an asset and its project related to the given repo URL"""
        try:
            with self.get_session() as session:
                # Clean up the URL for comparison
                repo_url = repo_url.rstrip('/')
                if repo_url.endswith('.git'):
                    repo_url = repo_url[:-4]
                
                # Query for assets with matching repo_url or file_url
                asset = session.query(Asset).filter(
                    or_(
                        Asset.source_url.like(f"{repo_url}%"),
                    )
                ).first()
                
                if asset:
                    # Get the first associated project
                    project = session.query(Project)\
                        .join(Project.assets)\
                        .filter(Asset.id == asset.id)\
                        .first()
                    return asset, project
                    
                return None
                
        except Exception as e:
            self.logger.error(f"Error searching for related asset: {str(e)}")
            return None
            
    async def process_pr(self) -> str:
        """Process a pull request event"""
        # Extract relevant information
        pr = self.payload.get('pull_request', {})
        repo_url = self.payload.get('repo_url', '')
        
        # Basic PR info
        summary_lines = [
            f"🔍 New PR in {repo_url}\n",
            f"Title: {pr.get('title')}",
            f"Author: {pr.get('user', {}).get('login')}",
            f"Description: {pr.get('body', 'No description')}",
            f"URL: {pr.get('html_url')}\n",
            f"Changed files: {pr.get('changed_files', 0)}",
            f"Additions: {pr.get('additions', 0)}",
            f"Deletions: {pr.get('deletions', 0)}"
        ]
        
        # Look for related assets
        if repo_url:
            result = self.find_related_asset(repo_url)
            if result:
                asset, project = result
                summary_lines.extend([
                    "\n📁 Related Project Found:",
                    f"Project: {project.name}",
                    f"Description: {project.description}",
                    f"Type: {project.project_type}",
                    f"\nAsset Info:",
                    f"Type: {asset.asset_type}",
                    f"URL: {asset.repo_url or asset.file_url or asset.explorer_url}"
                ])
                
        return "\n".join(summary_lines)
        
    async def process_push(self) -> str:
        """Process a push event"""
        repo_url = self.payload.get('repo_url', '')
        commit = self.payload.get('commit', {})
        
        # Basic push info
        summary_lines = [
            f"📦 New commit in {repo_url}\n",
            f"Message: {commit.get('commit', {}).get('message', 'No message')}",
            f"Author: {commit.get('commit', {}).get('author', {}).get('name', 'Unknown')}",
            f"URL: {commit.get('html_url', '')}"
        ]
        
        # Look for related assets
        if repo_url:
            result = self.find_related_asset(repo_url)
            if result:
                asset, project = result
                summary_lines.extend([
                    "\n📁 Related Project Found:",
                    f"Project: {project.name}",
                    f"Description: {project.description}",
                    f"Type: {project.project_type}",
                    f"\nAsset Info:",
                    f"Type: {asset.asset_type}",
                    f"URL: {asset.repo_url or asset.file_url or asset.explorer_url}"
                ])
                
        return "\n".join(summary_lines)
        
    async def start(self) -> None:
        """Process the GitHub event"""
        try:
            self.status = JobStatus.RUNNING
            self.started_at = datetime.now(timezone.utc)
            
            # Process based on event type
            if self.event_type == 'pull_request':
                summary = await self.process_pr()
            elif self.event_type == 'push':
                summary = await self.process_push()
            else:
                raise ValueError(f"Unsupported event type: {self.event_type}")
            
            self.result = JobResult(
                success=True,
                message=summary,
                data=self.payload
            )
            
            # Send notification via Telegram
            telegram = TelegramService.get_instance()
            await telegram.send_message(summary)
            
            self.status = JobStatus.COMPLETED
            self.completed_at = datetime.now(timezone.utc)
            
        except Exception as e:
            self.logger.error(f"Failed to process GitHub event: {str(e)}")
            self.status = JobStatus.FAILED
            self.error = str(e)
            raise
            
    async def stop(self) -> None:
        """Stop the job"""
        if self.status == JobStatus.RUNNING:
            self.status = JobStatus.CANCELLED

class GitHubEventHandler(Handler):
    """Handler for GitHub events (PR and push)"""
    
    def __init__(self):
        super().__init__()
        self.logger = Logger("GitHubEventHandler")
    
    @classmethod
    def get_triggers(cls) -> List[HandlerTrigger]:
        """Get list of triggers this handler listens for"""
        return [HandlerTrigger.GITHUB_PR, HandlerTrigger.GITHUB_PUSH]
    
    async def handle(self) -> None:
        """Handle a GitHub event"""
        if not self.context:
            self.logger.error("No context provided")
            return
            
        # Get the event data from the context
        event_data = self.context
        if not event_data:
            self.logger.error("No event data in context")
            return
            
        # Determine event type from trigger
        if self.trigger == HandlerTrigger.GITHUB_PR:
            event_type = 'pull_request'
        elif self.trigger == HandlerTrigger.GITHUB_PUSH:
            event_type = 'push'
        else:
            self.logger.error(f"Unsupported trigger: {self.trigger}")
            return
            
        # Create and submit job
        job = GitHubEventJob(event_type, event_data)
        job_manager = JobManager()
        await job_manager.submit_job(job) 