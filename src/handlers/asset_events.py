from typing import List, Union, Dict, Any, Optional
from src.handlers.base import Handler, HandlerTrigger, HandlerResult
from src.services.db_notification_service import DatabaseNotificationService
from src.util.logging import Logger
from src.models.base import Asset, AssetType
import difflib
import io
from datetime import datetime


class AssetEventHandler(Handler):
    """Handler for asset-related events"""

    def __init__(self):
        super().__init__()
        self.logger = Logger("AssetEventHandler")
        self.notification_service = DatabaseNotificationService.get_instance()

    @classmethod
    def get_triggers(cls) -> List[HandlerTrigger]:
        """Get list of triggers this handler listens for"""
        return [HandlerTrigger.NEW_ASSET, HandlerTrigger.ASSET_UPDATE, HandlerTrigger.ASSET_REMOVE]

    async def handle(self) -> HandlerResult:
        """Handle the event based on trigger type"""
        try:
            if not self.context or not self.trigger:
                return HandlerResult(success=False, data={"error": "Missing context or trigger"})

            self.logger.debug(f"Handler received context with keys: {list(self.context.keys())}")

            if self.trigger == HandlerTrigger.ASSET_UPDATE:
                return await self._handle_asset_update(
                    asset=self.context.get("asset"),
                    old_path=self.context.get("old_path"),
                    new_path=self.context.get("new_path"),
                    old_revision=self.context.get("old_revision"),
                    new_revision=self.context.get("new_revision"),
                    old_code=self.context.get("old_code"),
                    new_code=self.context.get("new_code"),
                )
            elif self.trigger == HandlerTrigger.ASSET_REMOVE:
                result = await self._handle_asset_removal(self.context.get("asset"))
            else:
                result = await self._handle_new_asset(self.context.get("asset"))

            return HandlerResult(success=True, data=result)

        except Exception as e:
            self.logger.error(f"Failed to handle asset event: {str(e)}")
            return HandlerResult(success=False, data={"error": str(e)})

    def _get_asset_attr(self, asset: Union[Asset, Dict[str, Any]], attr: str, default: Any = None) -> Any:
        """Helper method to get attribute from either Asset object or dictionary"""
        if isinstance(asset, dict):
            return asset.get(attr, default)
        return getattr(asset, attr, default)

    async def _handle_asset_update(
        self,
        asset: Union[Asset, Dict[str, Any]],
        old_path: Optional[str],
        new_path: Optional[str],
        old_revision: Optional[str],
        new_revision: Optional[str],
        old_code: Optional[str] = None,
        new_code: Optional[str] = None,
    ) -> dict:
        """Handle asset update"""
        project_name = self._get_asset_attr(asset, "project").name if hasattr(asset, "project") else "Unknown Project"
        source_url = self._get_asset_attr(asset, "source_url", "N/A")
        asset_type = self._get_asset_attr(asset, "asset_type", "N/A")

        self.logger.debug(f"Handler received - old_code: {bool(old_code)}, new_code: {bool(new_code)}")
        self.logger.debug(f"Asset type in handler: {asset_type}")

        message_parts = ["📝 Asset Updated", f"🔗 Project: {project_name}", f"🔗 URL: {source_url}", f"📁 Type: {asset_type}"]

        # Show revision changes and diffs if revisions are different
        if old_revision is not None and new_revision is not None and old_revision != new_revision:
            message_parts.append(f"📝 Revision: {old_revision} → {new_revision}")

            if old_code and new_code and asset_type in [AssetType.GITHUB_FILE, AssetType.DEPLOYED_CONTRACT]:
                message_parts.append("\nℹ️ Code diff available but not shown in this notification.")
            elif asset_type == AssetType.GITHUB_REPO:
                message_parts.append("\nℹ️ No diff available for repository updates")
            else:
                message_parts.append("\nℹ️ Code comparison not available")

        await self.notification_service.send_message("\n".join(message_parts))

        return HandlerResult(
            success=True,
            data={
                "event": "asset_updated",
                "project": project_name,
                "source_url": source_url,
                "old_revision": old_revision,
                "new_revision": new_revision,
            },
        )

    def _create_html_diff(
        self, old_code: str, new_code: str, old_title: str, new_title: str, project_name: str, source_url: str
    ) -> str:
        """Create an HTML diff view with syntax highlighting"""
        old_lines = old_code.splitlines()
        new_lines = new_code.splitlines()

        diff = difflib.HtmlDiff()
        html = diff.make_file(old_lines, new_lines, fromdesc=old_title, todesc=new_title, context=True)

        # Enhance the HTML with better styling
        enhanced_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Code Diff - {project_name}</title>
            <style>
                body {{
                    font-family: monospace;
                    margin: 0;
                    padding: 20px;
                    background: #f5f5f5;
                }}
                .header {{
                    background: #fff;
                    padding: 20px;
                    margin-bottom: 20px;
                    border-radius: 5px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                }}
                .diff {{
                    background: #fff;
                    padding: 20px;
                    border-radius: 5px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                    overflow-x: auto;
                }}
                table.diff {{
                    font-family: monospace;
                    border-collapse: collapse;
                    width: 100%;
                }}
                .diff td {{
                    padding: 1px 4px;
                    vertical-align: top;
                    white-space: pre;
                    font-size: 14px;
                }}
                .diff_header {{
                    background-color: #f8f8f8;
                }}
                td.diff_header {{
                    text-align: right;
                    padding: 1px 4px;
                    border-right: 1px solid #ddd;
                    background-color: #f8f8f8;
                    width: 40px;
                }}
                .diff_next {{
                    background-color: #f8f8f8;
                    padding: 1px 4px;
                }}
                .diff_add {{
                    background-color: #e6ffe6;
                }}
                .diff_chg {{
                    background-color: #fff3d4;
                }}
                .diff_sub {{
                    background-color: #ffe6e6;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>{project_name}</h2>
                <p>Source: <a href="{source_url}">{source_url}</a></p>
                <p>Comparing {old_title} with {new_title}</p>
            </div>
            <div class="diff">
        """

        # Insert our enhanced header and style
        html = html.replace("<html>", enhanced_html)

        # Close the diff div
        html = html.replace("</body>", "</div></body>")

        return html

    async def _handle_asset_removal(self, asset: Union[Asset, Dict[str, Any]]) -> dict:
        """Handle asset removal"""
        project_name = self._get_asset_attr(asset, "project").name if hasattr(asset, "project") else "Unknown Project"
        source_url = self._get_asset_attr(asset, "source_url", "N/A")

        message = f"❌ Asset Removed\n🔗 Project: {project_name}\n🔗 URL: {source_url}"
        await self.notification_service.send_message(message)

        return {"event": "asset_removed", "project": project_name, "source_url": source_url}

    async def _handle_new_asset(self, asset: Union[Asset, Dict[str, Any]]) -> dict:
        """Handle new asset"""
        project_name = self._get_asset_attr(asset, "project").name if hasattr(asset, "project") else "Unknown Project"
        source_url = self._get_asset_attr(asset, "source_url", "N/A")
        asset_type = self._get_asset_attr(asset, "asset_type", "N/A")

        message = ["🆕 New Asset Added", f"🔗 Project: {project_name}", f"🔗 URL: {source_url}", f"📁 Type: {asset_type}"]

        await self.notification_service.send_message("\n".join(message))

        return {"event": "new_asset", "project": project_name, "source_url": source_url}
