from typing import List, Dict, Any
from src.jobs.watcher import WatcherJob
from src.util.logging import Logger
from src.config.config import Config
from src.handlers.base import HandlerTrigger
from aiohttp import web
from src.watchers.webhook_server import WebhookServer
import json

class GitHubWatcher(WatcherJob):
    """Watcher that handles GitHub webhook events"""
    
    def __init__(self):
        super().__init__("github", interval=0)  # interval=0 since we use webhooks
        self.logger = Logger("GitHubWatcher")
        self.config = Config()
        self.webhook_secret = self.config.get('github', {}).get('webhook_secret')
        
    async def initialize(self) -> None:
        """Initialize the webhook server"""
        if not self.webhook_secret:
            raise ValueError("GitHub webhook secret not configured")
            
        # Get shared webhook server instance
        webhook_server = await WebhookServer.get_instance()
        
        # Register our endpoint
        webhook_server.register_endpoint('/github', self.handle_webhook)
        self.logger.info("Registered GitHub webhook endpoint")
        
    async def check(self) -> List[Dict[str, Any]]:
        """Not used since we're webhook-based"""
        return []
        
    async def handle_webhook(self, request: web.Request) -> web.Response:
        """Handle incoming GitHub webhook events"""
        try:
            # Log headers for debugging
            self.logger.info(f"Received GitHub webhook headers: {dict(request.headers)}")
            
            # Verify webhook signature
            if not await self.verify_signature(request):
                return web.Response(status=401, text="Invalid signature")
            
            # Handle both JSON and form-encoded payloads
            content_type = request.headers.get('Content-Type', '')
            
            if 'application/x-www-form-urlencoded' in content_type:
                # Parse form data
                form_data = await request.post()
                if 'payload' not in form_data:
                    return web.Response(status=400, text="Missing payload in form data")
                try:
                    payload = json.loads(form_data['payload'])
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse form payload JSON: {e}")
                    return web.Response(status=400, text=f"Invalid JSON in form payload: {str(e)}")
            else:
                # Handle direct JSON payload
                try:
                    payload = await request.json()
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse JSON payload: {e}")
                    return web.Response(status=400, text=f"Invalid JSON payload: {str(e)}")
            
            event_type = request.headers.get('X-GitHub-Event')
            self.logger.info(f"Received GitHub webhook: {event_type}")
            
            # Handle different event types
            events = []
            if event_type == 'push':
                events.extend(await self.handle_push_event(payload))
            elif event_type == 'pull_request':
                events.extend(await self.handle_pr_event(payload))
            
            # Trigger handlers for the events
            for event in events:
                self.event_bus.trigger_event(event['trigger'], event['data'])
                
            return web.Response(status=200, text="OK")
            
        except Exception as e:
            self.logger.error(f"Error handling webhook: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return web.Response(status=500, text=f"Internal error: {str(e)}")
            
    async def verify_signature(self, request: web.Request) -> bool:
        """Verify GitHub webhook signature"""
        try:
            # Get signature from header
            signature = request.headers.get('X-Hub-Signature-256')
            if not signature:
                return False
                
            # TODO: Implement signature verification using webhook secret
            # For now, accept all requests in development
            return True
            
        except Exception as e:
            self.logger.error(f"Error verifying signature: {e}")
            return False
            
    async def handle_push_event(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Handle GitHub push events"""
        events = []
        
        try:
            repo_name = payload['repository']['full_name']
            branch = payload['ref'].split('/')[-1]
            commits = payload['commits']
            
            # Create event for new commits
            events.append({
                'trigger': HandlerTrigger.GITHUB_PUSH,
                'data': {
                    'repository': repo_name,
                    'branch': branch,
                    'commits': commits
                }
            })
            
        except Exception as e:
            self.logger.error(f"Error handling push event: {e}")
            
        return events
        
    async def handle_pr_event(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Handle GitHub pull request events"""
        events = []
        
        try:
            action = payload['action']
            pr = payload['pull_request']
            repo_name = payload['repository']['full_name']
            
            # Create event for PR updates
            events.append({
                'trigger': HandlerTrigger.GITHUB_PR,
                'data': {
                    'repository': repo_name,
                    'action': action,
                    'pull_request': {
                        'number': pr['number'],
                        'title': pr['title'],
                        'body': pr['body'],
                        'state': pr['state'],
                        'url': pr['html_url']
                    }
                }
            })
            
        except Exception as e:
            self.logger.error(f"Error handling PR event: {e}")
            
        return events
        
    async def stop(self) -> None:
        """Stop the webhook server"""
        # No need to stop the webhook server as it's managed by WebhookServer