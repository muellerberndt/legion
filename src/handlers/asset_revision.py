from typing import List
from src.handlers.base import Handler, HandlerTrigger
from src.models.base import Asset
from src.util.logging import Logger
from src.util.diff import compute_file_diff
from src.models.base import AssetType

class AssetRevisionHandler(Handler):
    """Handler that tracks asset revisions and computes diffs for files"""
    
    def __init__(self):
        super().__init__()
        self.logger = Logger("AssetRevisionHandler")
        
    @classmethod
    def get_triggers(cls) -> List[HandlerTrigger]:
        """Get list of triggers this handler listens for"""
        return [HandlerTrigger.ASSET_UPDATE]
        
    async def handle(self) -> None:
        """Handle an asset update event"""
        if not self.context:
            self.logger.error("No context provided")
            return
            
        asset = self.context.get('asset')
        if not asset:
            self.logger.error("No asset in context")
            return
            
        old_revision = self.context.get('old_revision')
        new_revision = self.context.get('new_revision')
        removed = self.context.get('removed', False)
        
        if removed:
            self.logger.info(f"Asset {asset.id} removed")
            return
            
        self.logger.info(f"Asset {asset.id} updated from revision {old_revision} to {new_revision}")
        
        # For files, compute and store diff
        if asset.asset_type == AssetType.GITHUB_FILE:
            old_path = self.context.get('old_path')
            new_path = self.context.get('new_path')
            
            if old_path and new_path:
                try:
                    diff_result = await compute_file_diff(old_path, new_path)
                    if diff_result and diff_result.has_changes:
                        # Store diff in asset metadata
                        asset.extra_data = asset.extra_data or {}
                        asset.extra_data['diff'] = diff_result.to_dict()
                        
                        # Log summary of changes
                        self.logger.info(
                            f"Changes detected in {asset.id}:\n"
                            f"- {len(diff_result.added_lines)} lines added\n"
                            f"- {len(diff_result.removed_lines)} lines removed\n"
                            f"- {len(diff_result.modified_lines)} lines modified"
                        )
                    else:
                        self.logger.info(f"No changes detected in file content for {asset.id}")
                        
                except Exception as e:
                    self.logger.error(f"Failed to compute diff for {asset.id}: {str(e)}")
            else:
                self.logger.warning(f"Missing old_path or new_path for file diff of {asset.id}") 