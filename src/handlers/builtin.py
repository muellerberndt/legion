"""Built-in handlers registration"""

from typing import List, Type
from src.handlers.base import Handler
from src.handlers.github_events import GitHubEventHandler
from src.handlers.project_events import ProjectEventHandler


def get_builtin_handlers() -> List[Type[Handler]]:
    """Get all built-in handlers that should be registered by default"""
    return [GitHubEventHandler, ProjectEventHandler]
