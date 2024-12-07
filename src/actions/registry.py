from typing import Dict, Type, Optional, Tuple, Callable
from src.actions.base import BaseAction, ActionSpec
from src.util.logging import Logger
from src.actions.result import ActionResult
from src.actions.builtin import get_builtin_actions


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

        # Register built-in actions
        for action_class in get_builtin_actions():
            self.register_action(action_class.spec.name, action_class)
            self.logger.info(f"Registered built-in action: {action_class.spec.name}")

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
                if action_class.__name__ == "SemanticSearchAction" and args:
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
