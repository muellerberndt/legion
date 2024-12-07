from typing import List, Dict, Any
from src.handlers.base import Handler, HandlerTrigger
from src.models.base import Project
from src.util.logging import Logger
from src.services.notification_service import NotificationService

class ProjectEventHandler(Handler):
    """Handler that tracks project additions, updates, and removals"""
    
    def __init__(self):
        super().__init__()
        self.logger = Logger("ProjectEventHandler")
        self.notification_service = NotificationService.get_instance()
        
    @classmethod
    def get_triggers(cls) -> List[HandlerTrigger]:
        """Get list of triggers this handler listens for"""
        return [
            HandlerTrigger.NEW_PROJECT,
            HandlerTrigger.PROJECT_UPDATE,
            HandlerTrigger.PROJECT_REMOVE
        ]
        
    async def handle(self) -> None:
        """Handle project events"""
        if not self.context:
            self.logger.error("No context provided")
            return
            
        project = self.context.get('project')
        if not project:
            self.logger.error("No project in context")
            return
            
        old_project = self.context.get('old_project')  # For updates
        removed = self.context.get('removed', False)
        
        if removed:
            await self._handle_project_removal(project)
        elif old_project:
            await self._handle_project_update(old_project, project)
        else:
            await self._handle_new_project(project)
            
    async def _handle_new_project(self, project: Project) -> None:
        """Handle new project addition"""
        message = (
            f"🆕 New Project Added\n"
            f"Name: {project.name}\n"
            f"Type: {project.project_type}\n"
            f"Description: {project.description}\n"
            f"Assets: {len(project.assets)}"
        )
        
        if project.extra_data:
            message += "\nAdditional Info:"
            for key, value in project.extra_data.items():
                message += f"\n- {key}: {value}"
                
        self.logger.info(f"New project added: {project.name}")
        await self.notification_service.send_message(message)
        
    async def _handle_project_update(self, old_project: Project, new_project: Project) -> None:
        """Handle project update"""
        changes = []
        
        # Check basic attributes
        if old_project.name != new_project.name:
            changes.append(f"Name: {old_project.name} → {new_project.name}")
            
        if old_project.description != new_project.description:
            changes.append(f"Description updated")
            
        if old_project.project_type != new_project.project_type:
            changes.append(f"Type: {old_project.project_type} → {new_project.project_type}")
            
        # Check extra data changes
        old_extra = old_project.extra_data or {}
        new_extra = new_project.extra_data or {}
        
        for key in set(old_extra.keys()) | set(new_extra.keys()):
            old_value = old_extra.get(key)
            new_value = new_extra.get(key)
            if old_value != new_value:
                changes.append(f"{key}: {old_value} → {new_value}")
                
        # Check asset changes
        old_assets = {a.id: a for a in old_project.assets}
        new_assets = {a.id: a for a in new_project.assets}
        
        added_assets = set(new_assets.keys()) - set(old_assets.keys())
        removed_assets = set(old_assets.keys()) - set(new_assets.keys())
        
        if added_assets:
            changes.append(f"Added {len(added_assets)} new assets")
        if removed_assets:
            changes.append(f"Removed {len(removed_assets)} assets")
            
        if changes:
            message = (
                f"📝 Project Updated: {new_project.name}\n"
                f"Changes detected:\n- " + "\n- ".join(changes)
            )
            
            self.logger.info(f"Project updated: {new_project.name}")
            await self.notification_service.send_message(message)
        else:
            self.logger.debug(f"No significant changes detected for project: {new_project.name}")
            
    async def _handle_project_removal(self, project: Project) -> None:
        """Handle project removal"""
        message = (
            f"🗑️ Project Removed\n"
            f"Name: {project.name}\n"
            f"Type: {project.project_type}\n"
            f"Assets removed: {len(project.assets)}"
        )
        
        self.logger.info(f"Project removed: {project.name}")
        await self.notification_service.send_message(message) 