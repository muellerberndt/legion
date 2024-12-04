from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Type, Callable
from functools import wraps

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
    is_async: bool = False  # Whether this action spawns a job

def AsyncAction(action_class: Type) -> Type:
    """Decorator to mark an action as asynchronous (spawns a job)"""
    if not hasattr(action_class, 'spec'):
        raise ValueError(f"Action class {action_class.__name__} must have a spec attribute")
    
    # Mark the action as async
    action_class.spec.is_async = True
    return action_class

class BaseAction(ABC):
    """Base class for all actions"""
    
    spec: Optional[ActionSpec] = None
    
    @abstractmethod
    def execute(self) -> Any:
        """Execute the action"""
        pass
    
    @classmethod
    def is_async(cls) -> bool:
        """Check if this action is asynchronous (spawns a job)"""
        return hasattr(cls, 'spec') and cls.spec.is_async