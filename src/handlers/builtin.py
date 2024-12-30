"""Built-in handlers registration"""

from typing import List, Type
from src.handlers.base import Handler
from src.handlers.project_events import ProjectEventHandler
from src.handlers.asset_events import AssetEventHandler
from src.handlers.github_event import GitHubEventHandler
from src.handlers.proxy_upgrade import ProxyUpgradeHandler


def get_builtin_handlers() -> List[Type[Handler]]:
    """Get all built-in handlers that should be registered by default"""
    return [ProjectEventHandler, AssetEventHandler, GitHubEventHandler, ProxyUpgradeHandler]
