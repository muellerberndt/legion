from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, List, Optional, Callable


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
    help_text: str  # Detailed help text shown with /help <command>
    agent_hint: str  # Hint for agents about when/how to use this command
    arguments: List[ActionArgument] = None


class BaseAction(ABC):
    """Base class for all actions"""

    spec: Optional[ActionSpec] = None

    def __init__(self):
        self._update_callback = None

    def set_update_callback(self, callback: Callable[[str], None]) -> None:
        """Set a callback for progress updates"""
        self._update_callback = callback

    async def send_update(self, message: str) -> None:
        """Send a progress update"""
        if self._update_callback:
            await self._update_callback(message)

    @abstractmethod
    async def execute(self, *args, **kwargs) -> Any:
        """Execute the action"""
