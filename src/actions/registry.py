from typing import Dict, Type, Optional, Tuple, Callable, List
from src.actions.base import BaseAction, ActionSpec
from src.util.logging import Logger
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
                # Pass args or kwargs directly to execute
                if args:
                    result = await action.execute(*args)
                else:
                    result = await action.execute(**kwargs)
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

    def _get_agent_command_instructions(self, command_names: Optional[List[str]] = None) -> Dict[str, ActionSpec]:
        """Get the commands available to this component"""
        commands = {}

        # Get all registered actions
        actions = self.get_actions()
        self.logger.info("Found registered actions:", extra_data={"available_actions": list(actions.keys())})

        # If command_names is None, include ALL commands (for Chatbot)
        if command_names is None:
            # Filter out actions marked with @no_autobot
            command_names = []
            for name, (handler, spec) in actions.items():
                # Get the original action class from the registry
                action_class = None
                for cls in BaseAction.__subclasses__():
                    if cls.spec.name == name:
                        action_class = cls
                        break

                # Skip if action is marked with @no_autobot
                if action_class and not hasattr(action_class, "_no_autobot"):
                    command_names.append(name)

            self.logger.info("Including available commands (filtered for Autobot)")
        elif not command_names:
            self.logger.info("No commands specified")
            return commands

        self.logger.info("Filtering actions by command names:", extra_data={"requested_commands": command_names})

        # Get action specs
        for name, (_, spec) in actions.items():
            if name in command_names:
                if not spec:
                    self.logger.warning(f"Action {name} has no spec, skipping")
                    continue
                commands[name] = spec

        self.logger.info("Initialized commands:", extra_data={"available_commands": list(commands.keys())})
        return commands
