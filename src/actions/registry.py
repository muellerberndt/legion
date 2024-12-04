from typing import Dict, Type, Optional, Tuple, Callable
from src.actions.base import BaseAction, ActionSpec
from src.util.logging import Logger
from src.interfaces.base import Message
from src.actions.result import ActionResult

# Import all actions
from src.actions.help import HelpAction
from src.actions.database_search import DatabaseSearchAction
from src.actions.semantic_search import SemanticSearchAction
from src.actions.generate_embeddings import GenerateEmbeddingsAction
from src.actions.delete_embeddings import DeleteEmbeddingsAction
from src.actions.agent import AgentAction
from src.actions.job import GetJobResultAction, StopJobAction
from src.actions.sync.immunefi import ImmunefiSyncAction

class ActionRegistry:
    """Registry for all available actions"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ActionRegistry, cls).__new__(cls)
            cls._instance.initialize()
        return cls._instance
        
    def initialize(self):
        self.logger = Logger("ActionRegistry")
        self.actions: Dict[str, Tuple[Callable, ActionSpec]] = {}
        
        # Register built-in actions
        self.register_action("help", HelpAction)
        self.register_action("db_search", DatabaseSearchAction)
        self.register_action("sem_search", SemanticSearchAction)
        self.register_action("embeddings", GenerateEmbeddingsAction)
        self.register_action("delete_embeddings", DeleteEmbeddingsAction)
        self.register_action("agent", AgentAction)
        self.register_action("job", GetJobResultAction)
        self.register_action("stop", StopJobAction)
        self.register_action("sync", ImmunefiSyncAction)
        
    def register_action(self, name: str, action_class: Type[BaseAction]) -> None:
        """Register an action class"""
        handler = self.create_handler(action_class)
        self.actions[name] = (handler, action_class.spec)
        self.logger.info(f"Registered action: {name}")
        
    def create_handler(self, action_class: Type[BaseAction]) -> Callable:
        """Create handler for an action class"""
        async def handler(message: Message, *args, **kwargs) -> str:
            try:
                action = action_class()
                # For search actions, prepend "search" to the query
                if action_class in [DatabaseSearchAction, SemanticSearchAction]:
                    query = f"search {' '.join(args)}"
                    result = await action.execute(query)
                # For agent action, join all args into a single prompt
                elif action_class == AgentAction:
                    prompt = ' '.join(args)
                    result = await action.execute(prompt)
                else:
                    # For other actions, pass args as is
                    if len(args) == 1:
                        result = await action.execute(args[0])
                    else:
                        result = await action.execute(*args)
                    
                if isinstance(result, ActionResult):
                    return result.content
                return str(result)
            except Exception as e:
                self.logger.error(f"Action failed: {str(e)}")
                raise
        return handler
        
    def get_action(self, name: str) -> Optional[Tuple[Callable, ActionSpec]]:
        """Get an action by name"""
        return self.actions.get(name)
        
    def get_actions(self) -> Dict[str, Tuple[Callable, ActionSpec]]:
        """Get all registered actions"""
        return self.actions