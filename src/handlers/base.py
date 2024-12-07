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
    BLOCKCHAIN_EVENT = auto()

    @classmethod
    def register_custom_trigger(cls, trigger_name: str) -> "HandlerTrigger":
        """Register a custom trigger if it doesn't exist yet"""
        try:
            return cls[trigger_name]
        except KeyError:
            # Create a new enum member
            value = len(cls.__members__) + 1
            new_member = object.__new__(cls)
            new_member._value_ = value
            new_member._name_ = trigger_name
            cls._value2member_map_[value] = new_member
            cls.__members__[trigger_name] = new_member
            return new_member


class Handler(ABC):
    """Base class for event handlers"""

    def __init__(self):
        self.context = {}
        self.trigger = None

    @classmethod
    @abstractmethod
    def get_triggers(cls) -> List[HandlerTrigger]:
        """Get list of triggers this handler listens for"""

    @abstractmethod
    def handle(self) -> None:
        """Handle an event"""

    def set_context(self, context: Dict[str, Any], trigger: HandlerTrigger = None) -> None:
        """Set context and trigger for this handler"""
        self.context = context
        self.trigger = trigger
