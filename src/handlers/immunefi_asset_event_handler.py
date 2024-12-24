from typing import List
from src.handlers.base import Handler, HandlerTrigger, HandlerResult
from src.util.logging import Logger
from src.services.telegram import TelegramService


class ImmunefiAssetEventHandler(Handler):
    """Handler for Immunefi asset events"""

    def __init__(self):
        super().__init__()
        self.logger = Logger("ImmunefiAssetEventHandler")
        self.telegram = TelegramService.get_instance()

    @classmethod
    def get_triggers(cls) -> List[HandlerTrigger]:
        """Get list of triggers this handler listens for"""
        return [HandlerTrigger.ASSET_UPDATE, HandlerTrigger.NEW_ASSET]

    async def handle(self) -> HandlerResult:
        """Handle asset events"""
        self.logger.info(f"Handling asset event: {self.trigger}")
        self.logger.debug("Context received:", extra_data={"context": self.context})

        if not self.context:
            self.logger.error("No context provided")
            return HandlerResult(success=False, data={"error": "No context provided"})

        asset = self.context.get("asset")
        if not asset:
            self.logger.error("No asset in context")
            return HandlerResult(success=False, data={"error": "No asset in context"})

        # Get project either from relationship or context
        project = getattr(asset, "project", None) or self.context.get("project")
        if not project:
            self.logger.error("No project associated with asset")
            return HandlerResult(success=False, data={"error": "No project associated with asset"})

        # Build message based on event type
        if self.trigger == HandlerTrigger.NEW_ASSET:
            message = [
                "🆕 New Asset Added\n",
                f"🔗 Project: {project.name}",
                f"🔗 URL: {asset.source_url}",
                f"📁 Type: {asset.asset_type.value}",
            ]
        else:  # ASSET_UPDATE
            old_revision = self.context.get("old_revision")
            new_revision = self.context.get("new_revision")
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

        # Add diff info if available (for updates only)
        if self.trigger == HandlerTrigger.ASSET_UPDATE:
            old_path = self.context.get("old_path")
            new_path = self.context.get("new_path")
            if old_path and new_path:
                message.append("💾 File diff available")

        # Send notification
        await self.telegram.send_message("\n".join(message))

        return HandlerResult(
            success=True,
            data={
                "project": project.name,
                "asset_url": asset.source_url,
                "event_type": self.trigger.value,
                **(
                    {
                        "old_revision": self.context.get("old_revision"),
                        "new_revision": self.context.get("new_revision"),
                        "has_diff": bool(self.context.get("old_path") and self.context.get("new_path")),
                    }
                    if self.trigger == HandlerTrigger.ASSET_UPDATE
                    else {}
                ),
            },
        )
