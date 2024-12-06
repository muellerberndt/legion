from src.watchers.github import GitHubWatcher
from src.watchers.immunefi import ImmunefiWatcher
from src.watchers.quicknode import QuicknodeWatcher
from src.util.logging import Logger

class WatcherRegistry:
    """Registry for all watchers"""
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(WatcherRegistry, cls).__new__(cls)
        return cls._instance
        
    def initialize(self):
        """Initialize the registry"""
        if self._initialized:
            return
            
        self.logger = Logger("WatcherRegistry")
        self.watchers = {
            "github": GitHubWatcher,
            "immunefi": ImmunefiWatcher,
            "quicknode": QuicknodeWatcher
        }
        self._initialized = True
        
    def get_watcher(self, name: str):
        """Get a watcher by name"""
        return self.watchers.get(name) 