from typing import List, Union, Dict, Any
from src.handlers.base import Handler, HandlerTrigger, HandlerResult
from src.services.telegram import TelegramService
from src.util.logging import Logger
from src.models.base import Project


class ProjectEventHandler(Handler):
    """Handler for project-related events"""

    def __init__(self):
        super().__init__()
        self.logger = Logger("ProjectEventHandler")
        self.telegram = TelegramService.get_instance()
        self.logger.debug(f"Telegram service initialized: {bool(self.telegram)}")
        self.logger.debug(f"Telegram bot initialized: {bool(self.telegram.bot)}")
        self.logger.debug(f"Telegram chat_id configured: {bool(self.telegram.chat_id)}")

    @classmethod
    def get_triggers(cls) -> List[HandlerTrigger]:
        """Get list of triggers this handler listens for"""
        return [HandlerTrigger.NEW_PROJECT, HandlerTrigger.PROJECT_UPDATE, HandlerTrigger.PROJECT_REMOVE]

    async def handle(self) -> HandlerResult:
        """Handle project events"""
        try:
            if not self.context:
                self.logger.error("No context provided")
                return HandlerResult(success=False, data={"error": "No context provided"})

            self.logger.debug(
                "Event details:",
                extra_data={
                    "old_project": self.context.get("old_project"),
                    "removed": self.context.get("removed", False),
                    "trigger": self.trigger.name if self.trigger else None,
                    "context_keys": list(self.context.keys()),
                    "project_data": self.context.get("project"),
                },
            )

            project_data = self.context.get("project")
            if not project_data:
                self.logger.error("No project data in context")
                return HandlerResult(success=False, data={"error": "No project data in context"})

            old_project = self.context.get("old_project")
            removed = self.context.get("removed", False)

            self.logger.debug(f"Processing event - Removed: {removed}, Old project exists: {old_project is not None}")

            result = None
            if removed:
                self.logger.info("Handling project removal")
                result = await self._handle_project_removal(project_data)
            elif old_project:
                self.logger.info("Handling project update")
                result = await self._handle_project_update(old_project, project_data)
            else:
                self.logger.info("Handling new project")
                result = await self._handle_new_project(project_data)

            return HandlerResult(success=True, data=result)

        except Exception as e:
            self.logger.error(f"Failed to handle project event: {str(e)}")
            return HandlerResult(success=False, data={"error": str(e)})

    def _get_project_attr(self, project: Union[Project, Dict[str, Any]], attr: str, default: Any = None) -> Any:
        """Helper method to get attribute from either Project object or dictionary"""
        if isinstance(project, dict):
            return project.get(attr, default)
        return getattr(project, attr, default)

    def _format_value(self, value: Any) -> str:
        """Format a value for display, converting lists to comma-separated strings"""
        if isinstance(value, list):
            return ", ".join(str(item) for item in value)
        return str(value)

    async def _handle_new_project(self, project: Union[Project, Dict[str, Any]]) -> dict:
        """Handle new project"""
        project_name = self._get_project_attr(project, "name")
        project_type = self._get_project_attr(project, "project_type")
        description = self._get_project_attr(project, "description")
        extra_data = self._get_project_attr(project, "extra_data", {})

        message = [
            "🆕 New Project Added",
            f"Name: {project_name}",
            f"Type: {project_type}",
        ]

        if description:
            message.append(f"Description: {description}")

        if extra_data:
            message.append("\nAdditional Info:")
            for key, value in extra_data.items():
                if value is not None:  # Only show non-None values
                    message.append(f"{key}: {self._format_value(value)}")

        await self.telegram.send_message("\n".join(message))
        return {"event": "new_project", "project_name": project_name, "project_type": project_type}

    async def _handle_project_removal(self, project: Union[Project, Dict[str, Any]]) -> dict:
        """Handle project removal"""
        project_name = self._get_project_attr(project, "name")
        message = f"❌ Project Removed: {project_name}"
        await self.telegram.send_message(message)
        return {"event": "project_removed", "project_name": project_name}

    async def _handle_project_update(
        self, old_project: Union[Project, Dict[str, Any]], new_project: Union[Project, Dict[str, Any]]
    ) -> dict:
        """Handle project update"""
        changes = []

        # Check basic attributes
        old_name = self._get_project_attr(old_project, "name")
        new_name = self._get_project_attr(new_project, "name")
        if old_name != new_name:
            changes.append(f"Name: {old_name} → {new_name}")

        old_desc = self._get_project_attr(old_project, "description")
        new_desc = self._get_project_attr(new_project, "description")
        if old_desc != new_desc:
            changes.append("Description updated")

        old_type = self._get_project_attr(old_project, "project_type")
        new_type = self._get_project_attr(new_project, "project_type")
        if old_type != new_type:
            changes.append(f"Type: {old_type} → {new_type}")

        # Check extra data changes
        old_extra = self._get_project_attr(old_project, "extra_data", {}) or {}
        new_extra = self._get_project_attr(new_project, "extra_data", {}) or {}

        for key in set(old_extra.keys()) | set(new_extra.keys()):
            old_value = old_extra.get(key)
            new_value = new_extra.get(key)
            if old_value != new_value:
                changes.append(f"{key}: {old_value} → {new_value}")

        # Check asset changes
        old_assets = {a.id: a for a in self._get_project_attr(old_project, "assets", [])}
        new_assets = {a.id: a for a in self._get_project_attr(new_project, "assets", [])}

        added_assets = set(new_assets.keys()) - set(old_assets.keys())
        removed_assets = set(old_assets.keys()) - set(new_assets.keys())

        if added_assets:
            changes.append(f"Added {len(added_assets)} new assets")
        if removed_assets:
            changes.append(f"Removed {len(removed_assets)} assets")

        if changes:
            message = f"📝 Project Updated: {new_name}\n" f"Changes detected:\n- " + "\n- ".join(changes)

            self.logger.info(f"Project updated: {new_name}")
            await self.telegram.send_message(message)
            return {"event": "project_updated", "project_name": new_name, "changes": changes}
        else:
            self.logger.debug(f"No significant changes detected for project: {new_name}")
            return {"event": "project_updated", "project_name": new_name, "changes": []}
