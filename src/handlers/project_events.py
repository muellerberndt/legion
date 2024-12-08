from typing import List
from src.handlers.base import Handler, HandlerTrigger
from src.models.base import Project
from src.util.logging import Logger
from src.services.telegram import TelegramService


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

    async def handle(self) -> None:
        """Handle project events"""
        try:
            if not self.context:
                self.logger.error("No context provided")
                return

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
                return

            old_project = self.context.get("old_project")
            removed = self.context.get("removed", False)

            self.logger.debug(f"Processing event - Removed: {removed}, Old project exists: {old_project is not None}")

            if removed:
                self.logger.info("Handling project removal")
                await self._handle_project_removal(project_data)
            elif old_project:
                self.logger.info("Handling project update")
                await self._handle_project_update(old_project, project_data)
            else:
                self.logger.info("Handling new project")
                await self._handle_new_project(project_data)

        except Exception as e:
            self.logger.error(f"Failed to handle project event: {str(e)}")
            raise

    async def _handle_new_project(self, project: dict) -> None:
        """Handle new project addition"""
        try:
            self.logger.debug("Building notification message for new project", extra_data={"project": project})

            message = (
                "🆕 gm ser! New Project Alert!\n\n"
                f"🎯 Project: {project.get('name')}\n"
                f"📝 Description: {project.get('description')}\n"
                f"💰 Max Bounty: ${project.get('extra_data', {}).get('maxBounty', 'Unknown')}\n"
                f"🔧 Type: {project.get('project_type')}\n"
                f"🌐 Ecosystem: {', '.join(project.get('extra_data', {}).get('ecosystem', []))}\n"
                f"💻 Language: {', '.join(project.get('extra_data', {}).get('language', []))}\n\n"
                "Based project ser, might be worth a look 👀"
            )

            # self.logger.debug("Message built, attempting to send", extra_data={"message": message})

            # if not self.telegram:
            #     self.logger.error("Telegram service not initialized")
            #     return

            # if not self.telegram.bot:
            #     self.logger.error("Telegram bot not initialized")
            #     return

            # if not self.telegram.chat_id:
            #     self.logger.error("Telegram chat_id not configured")
            #     return

            # self.logger.debug("Telegram service exists, sending message...")
            await self.telegram.send_message(message)
            self.logger.info(f"Successfully sent notification for new project: {project.get('name')}")

        except Exception as e:
            self.logger.error(f"Failed to send Telegram notification: {str(e)}")
            self.logger.error(f"Telegram service state - Bot: {bool(self.telegram.bot)}, Chat ID: {self.telegram.chat_id}")
            raise

    async def _handle_project_update(self, old_project: Project, new_project: Project) -> None:
        """Handle project update"""
        changes = []

        # Check basic attributes
        if old_project.name != new_project.name:
            changes.append(f"Name: {old_project.name} → {new_project.name}")

        if old_project.description != new_project.description:
            changes.append("Description updated")

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
            message = f"📝 Project Updated: {new_project.name}\n" f"Changes detected:\n- " + "\n- ".join(changes)

            self.logger.info(f"Project updated: {new_project.name}")
            await self.telegram.send_message(message)
        else:
            self.logger.debug(f"No significant changes detected for project: {new_project.name}")

    async def _handle_project_removal(self, project: Project) -> None:
        """Handle project removal"""
        message = (
            "🗑️ Project Removed\n\n"
            f"🎯 Project: {project.name}\n"
            f"💰 Type: {project.project_type}\n"
            f"📊 Assets removed: {len(project.assets)}\n\n"
            "ser, pour one out for another one gone 🫡"
        )

        self.logger.info(f"Project removed: {project.name}")
        await self.telegram.send_message(message)
