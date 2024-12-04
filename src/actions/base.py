from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Type, Callable

@dataclass
class ActionArgument:
    """Describes an action argument"""
    name: str
    description: str
    required: bool = True

@dataclass
class ActionSpec:
    """Specification for an action"""
    name: str
    description: str
    arguments: List[ActionArgument] = None

class BaseAction(ABC):
    """Base class for all actions"""
    
    spec: Optional[ActionSpec] = None
    
    @abstractmethod
    def execute(self) -> Any:
        """Execute the action"""
        pass