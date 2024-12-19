"""Built-in handlers registration"""

from typing import List, Type
from src.handlers.base import Handler
from src.handlers.project_events import ProjectEventHandler
from src.handlers.immunefi_asset_event_handler import ImmunefiAssetEventHandler
from src.handlers.github_event import GitHubEventHandler


def get_builtin_handlers() -> List[Type[Handler]]:
    """Get all built-in handlers that should be registered by default"""
    return [ProjectEventHandler, ImmunefiAssetEventHandler, GitHubEventHandler]
