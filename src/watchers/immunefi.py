from typing import List, Dict, Any
from src.jobs.watcher import WatcherJob
from src.actions.sync.immunefi import ImmunefiSyncAction
from src.handlers.base import HandlerTrigger

class ImmunefiWatcher(WatcherJob):
    """Watcher that periodically syncs Immunefi data"""
    
    def __init__(self):
        # Check every 24 hours
        super().__init__("immunefi", interval=24 * 60 * 60)
        self._sync_action = None
        
    @property
    def sync_action(self):
        """Lazy-load the sync action"""
        if self._sync_action is None:
            self._sync_action = ImmunefiSyncAction()
        return self._sync_action
        
    async def initialize(self) -> None:
        """Nothing to initialize"""
        pass
        
    async def check(self) -> List[Dict[str, Any]]:
        """Run Immunefi sync and return events"""
        try:
            # Run sync
            result = await self.sync_action.execute()
            self.logger.info(f"Immunefi sync completed: {result}")
            
            # Return sync event
            return [{
                'trigger': HandlerTrigger.SYNC_COMPLETED,
                'data': {
                    'source': 'immunefi',
                    'result': result
                }
            }]
            
        except Exception as e:
            self.logger.error(f"Immunefi sync failed: {str(e)}")
            return [] 