from typing import List
from src.handlers.base import Handler, HandlerTrigger
from src.models.base import Asset
from src.util.logging import Logger

class AssetRevisionHandler(Handler):
    """Handler that tracks asset revisions"""
    
    def __init__(self):
        super().__init__()
        self.logger = Logger("AssetRevisionHandler")
        
    @classmethod
    def get_triggers(cls) -> List[HandlerTrigger]:
        """Get list of triggers this handler listens for"""
        return [HandlerTrigger.ASSET_UPDATE]
        
    def handle(self) -> None:
        """Handle an asset update event"""
        if not self.context:
            self.logger.error("No context provided")
            return
            
        asset = self.context.get('asset')
        if not asset:
            self.logger.error("No asset in context")
            return
            
        self.logger.info(f"Asset {asset.id} updated") 