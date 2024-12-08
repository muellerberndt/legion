from typing import List
from src.handlers.base import Handler, HandlerTrigger
from src.util.logging import Logger
from src.services.telegram import TelegramService


class ImmunefiAssetEventHandler(Handler):
    """Handler for Immunefi asset update events"""

    def __init__(self):
        super().__init__()
        self.logger = Logger("ImmunefiAssetEventHandler")
        self.telegram = TelegramService.get_instance()

    @classmethod
    def get_triggers(cls) -> List[HandlerTrigger]:
        """Get list of triggers this handler listens for"""
        return [HandlerTrigger.ASSET_UPDATE]

    async def handle(self) -> None:
        """Handle asset update events"""
        self.logger.info("Handling asset update event")
        self.logger.debug("Context received:", extra_data={"context": self.context})

        if not self.context:
            self.logger.error("No context provided")
            return

        asset = self.context.get("asset")
        if not asset:
            self.logger.error("No asset in context")
            return

        project = self.context.get("project")
        if not project:
            self.logger.error("No project in context")
            return

        old_revision = self.context.get("old_revision")
        new_revision = self.context.get("new_revision")

        # Build message
        message = [
            "🔄 Asset Updated\n",
            f"🔗 Project: {project.name}",
            f"🔗 URL: {asset.source_url}",
            f"📁 Type: {asset.asset_type.value}",
            f"📝 Revision: {old_revision} → {new_revision}\n",
        ]

        # Add bounty info if available
        if project.extra_data:
            max_bounty = project.extra_data.get("maxBounty")
            if max_bounty:
                message.append(f"💰 Max Bounty: ${max_bounty:,}")

            ecosystem = project.extra_data.get("ecosystem", [])
            if ecosystem:
                message.append(f"🌐 Ecosystem: {', '.join(ecosystem)}")

            product_type = project.extra_data.get("productType", [])
            if product_type:
                message.append(f"🏷️ Type: {', '.join(product_type)}")

            message.append("")  # Add empty line before diff info

        # Add diff info if available
        old_path = self.context.get("old_path")
        new_path = self.context.get("new_path")
        if old_path and new_path:
            message.append("💾 File diff available")

        # Send notification
        await self.telegram.send_message("\n".join(message))
