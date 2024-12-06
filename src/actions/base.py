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
    description: str  # Short one-line description for command list
    help_text: str   # Detailed help text shown with /help <command>
    agent_hint: str  # Hint for agents about when/how to use this command
    arguments: List[ActionArgument] = None

class BaseAction(ABC):
    """Base class for all actions"""
    
    spec: Optional[ActionSpec] = None
    
    @abstractmethod
    async def execute(self, *args, **kwargs) -> Any:
        """Execute the action"""
        pass