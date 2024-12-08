"""Built-in actions registration"""

from typing import List, Type
from src.actions.base import BaseAction
from src.actions.help import HelpAction
from src.actions.semantic_search import SemanticSearchAction
from src.actions.embeddings import EmbeddingsAction
from src.actions.file_search import FileSearchAction
from src.actions.db_query import DBQueryAction
from src.actions.job import ListJobsAction, GetJobResultAction, StopJobAction
from src.actions.sync.immunefi import ImmunefiSyncAction
from src.actions.status import StatusAction


def get_builtin_actions() -> List[Type[BaseAction]]:
    """Get all built-in actions that should be registered by default"""
    return [
        HelpAction,
        DBQueryAction,
        EmbeddingsAction,
        FileSearchAction,
        SemanticSearchAction,
        ListJobsAction,
        GetJobResultAction,
        StopJobAction,
        ImmunefiSyncAction,
        StatusAction,
    ]
