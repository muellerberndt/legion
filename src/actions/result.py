from dataclasses import dataclass
from typing import Optional


@dataclass
class ActionResult:
    """Result of an action execution"""

    content: str
    error: Optional[str] = None
