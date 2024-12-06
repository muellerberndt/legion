from typing import Dict, Type, Optional, Tuple, Callable
from src.actions.base import BaseAction, ActionSpec
from src.util.logging import Logger
from src.interfaces.base import Message
from src.actions.result import ActionResult

# Import all actions
from src.actions.help import HelpAction
from src.actions.semantic_search import SemanticSearchAction
from src.actions.embeddings import EmbeddingsAction
from src.actions.file_search import FileSearchAction
from src.actions.db_query import DBQueryAction
from src.actions.job import ListJobsAction, GetJobResultAction, StopJobAction
from src.actions.sync.immunefi import ImmunefiSyncAction

class ActionRegistry:
    """Registry for all available actions"""
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ActionRegistry, cls).__new__(cls)
        return cls._instance
        
    def initialize(self):
        """Initialize the registry if not already initialized"""
        if self._initialized:
            return
            
        self.logger = Logger("ActionRegistry")
        self.actions: Dict[str, Tuple[Callable, ActionSpec]] = {}
        
        self.logger.info("Initializing action registry")
        
        # Register core actions
        self.register_action("help", HelpAction)
        self.register_action("db_query", DBQueryAction)
        self.register_action("embeddings", EmbeddingsAction)
        self.register_action("files", FileSearchAction)
        self.register_action("semantic", SemanticSearchAction)
        
        # Register job management actions
        self.register_action("jobs", ListJobsAction)
        self.register_action("job", GetJobResultAction)
        self.register_action("stop", StopJobAction)
        
        # Register sync actions
        self.register_action("sync", ImmunefiSyncAction)
        
        self.logger.info("Action registry initialized with actions:", extra_data={
            "registered_actions": list(self.actions.keys())
        })
        
        self._initialized = True
        
    def register_action(self, name: str, action_class: Type[BaseAction]) -> None:
        """Register an action class"""
        handler = self.create_handler(action_class)
        self.actions[name] = (handler, action_class.spec)
        self.logger.info(f"Registered action: {name}")
        
    def create_handler(self, action_class: Type[BaseAction]) -> Callable:
        """Create handler for an action class"""
        async def handler(*args, **kwargs) -> str:
            try:
                action = action_class()
                
                # For semantic search, prepend "search" to the query
                if action_class == SemanticSearchAction and args:
                    query = f"search {' '.join(args)}"
                    result = await action.execute(query)
                else:
                    # For other actions, pass args as is
                    if args:
                        result = await action.execute(*args)
                    else:
                        result = await action.execute(**kwargs)
                    
                if isinstance(result, ActionResult):
                    return result.content
                return str(result)
            except Exception as e:
                self.logger.error(f"Action failed: {str(e)}")
                raise
        return handler
        
    def get_action(self, name: str) -> Optional[Tuple[Callable, ActionSpec]]:
        """Get an action by name"""
        if not self._initialized:
            self.initialize()
        return self.actions.get(name)
        
    def get_actions(self) -> Dict[str, Tuple[Callable, ActionSpec]]:
        """Get all registered actions"""
        if not self._initialized:
            self.initialize()
        return self.actions