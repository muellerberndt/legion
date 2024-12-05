from abc import ABC, abstractmethod
from typing import Dict, Any, List
from enum import Enum, auto

class HandlerTrigger(Enum):
    """Triggers that handlers can listen for"""
    NEW_PROJECT = auto()
    PROJECT_UPDATE = auto()
    PROJECT_REMOVE = auto()
    NEW_ASSET = auto()
    ASSET_UPDATE = auto()
    ASSET_REMOVE = auto()
    GITHUB_PUSH = auto()
    GITHUB_PR = auto()

class Handler(ABC):
    """Base class for event handlers"""
    
    def __init__(self):
        self.context = {}
        
    @classmethod
    @abstractmethod
    def get_triggers(cls) -> List[HandlerTrigger]:
        """Get list of triggers this handler listens for"""
        pass
        
    @abstractmethod
    def handle(self) -> None:
        """Handle an event"""
        pass
        
    def set_context(self, context: Dict[str, Any]) -> None:
        """Set context for this handler"""
        self.context = context