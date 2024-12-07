import importlib
import os
import sys
import inspect
from typing import Dict, Type, List
from src.actions.base import BaseAction
from src.handlers.base import Handler
from src.jobs.watcher import WatcherJob
from src.util.logging import Logger
from src.actions.registry import ActionRegistry
from src.handlers.registry import HandlerRegistry
from src.watchers.manager import WatcherManager
from src.agents.base_agent import BaseAgent
from src.config.config import Config

class ExtensionLoader:
    """Loads and manages extensions"""
    
    def __init__(self):
        self.logger = Logger("ExtensionLoader")
        self.extensions = {}
        self.action_registry = ActionRegistry()
        self.handler_registry = HandlerRegistry()
        self.watcher_manager = WatcherManager()
        self.config = Config()
        
    def _find_python_modules(self, directory: str) -> List[str]:
        """Find all Python modules in a directory recursively.
        
        Args:
            directory: Directory to search in
            
        Returns:
            List of module paths relative to the extensions directory
        """
        modules = []
        extensions_dir = self.config.get("extensions_dir", "extensions").strip("./")  # Remove ./ prefix if present
        base_dir = os.path.dirname(directory)  # Get the parent of the extension directory
        
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith('.py') and not file.startswith('_'):
                    # Get path relative to base_dir and convert to module path
                    rel_path = os.path.relpath(root, base_dir)
                    module_name = os.path.splitext(file)[0]
                    # Use configured extensions directory name
                    module_path = f"{extensions_dir}.{rel_path.replace(os.sep, '.')}.{module_name}"
                    modules.append(module_path)
                    
        return modules
        
    def _discover_components(self, module) -> Dict[str, List]:
        """Discover components in a module by inspecting all classes.
        
        Args:
            module: The module to inspect
            
        Returns:
            Dictionary containing discovered components by type
        """
        components = {
            'actions': {},
            'handlers': [],
            'watchers': [],
            'agents': []
        }
        
        # Get all members that are classes
        for name, member in inspect.getmembers(module, inspect.isclass):
            # Skip imported classes (only process classes defined in this module)
            if member.__module__ != module.__name__:
                continue
                
            # Check each type and add to appropriate list
            if issubclass(member, BaseAction) and member != BaseAction:
                components['actions'][member.spec.name] = member
            elif issubclass(member, Handler) and member != Handler:
                components['handlers'].append(member)
            elif issubclass(member, WatcherJob) and member != WatcherJob:
                components['watchers'].append(member)
            elif issubclass(member, BaseAgent) and member != BaseAgent:
                components['agents'].append(member)
                
        return components
        
    def load_extensions(self) -> None:
        """Load all extensions from the extensions directory"""
        extensions_dir = self.config.get("extensions_dir", "extensions")
        active_extensions = self.config.get("active_extensions", [])
        
        if not os.path.exists(extensions_dir):
            self.logger.info(f"Extensions directory {extensions_dir} not found")
            return
            
        self.logger.info(f"Loading extensions from {extensions_dir}")
        self.logger.info(f"Active extensions: {active_extensions}")
        
        # Add extensions dir to Python path if not already there
        if extensions_dir not in sys.path:
            sys.path.append(os.path.dirname(extensions_dir))
            
        # Process each extension directory
        for extension_dir in active_extensions:
            try:
                full_path = os.path.join(extensions_dir, extension_dir)
                if not os.path.exists(full_path):
                    self.logger.warning(f"Extension directory not found: {full_path}")
                    continue
                    
                # Load extension config if available
                config_path = os.path.join(full_path, "extra_config.yml")
                if os.path.exists(config_path):
                    self.config.load_extension_config(config_path)
                    
                # Find and load all Python modules in the directory
                modules = self._find_python_modules(full_path)
                
                # Initialize extension data
                self.extensions[extension_dir] = {
                    'actions': {},
                    'handlers': [],
                    'watchers': [],
                    'agents': []
                }
                
                # Import each module and collect components
                for module_path in modules:
                    try:
                        module = importlib.import_module(module_path)
                        components = self._discover_components(module)
                        
                        # Merge components into extension data
                        self.extensions[extension_dir]['actions'].update(components['actions'])
                        self.extensions[extension_dir]['handlers'].extend(components['handlers'])
                        self.extensions[extension_dir]['watchers'].extend(components['watchers'])
                        self.extensions[extension_dir]['agents'].extend(components['agents'])
                        
                    except Exception as e:
                        self.logger.error(f"Failed to load module {module_path}: {e}")
                        
                # Log found components
                components = self.extensions[extension_dir]
                self.logger.info(
                    f"Loaded extension directory: {extension_dir} - "
                    f"Found {len(components['actions'])} actions, "
                    f"{len(components['handlers'])} handlers, "
                    f"{len(components['watchers'])} watchers, "
                    f"{len(components['agents'])} agents"
                )
                
            except Exception as e:
                self.logger.error(f"Failed to load extension directory {extension_dir}: {e}")
                
    def register_components(self) -> None:
        """Register all components from loaded extensions"""
        for extension_dir, components in self.extensions.items():
            try:
                # Register actions
                for name, action_class in components['actions'].items():
                    self.action_registry.register_action(name, action_class)
                    self.logger.info(f"Registered action: {name}")
                    
                # Register handlers
                for handler_class in components['handlers']:
                    self.handler_registry.register_handler(handler_class)
                    self.logger.info(f"Registered handler: {handler_class.__name__}")
                    
                # Register watchers
                for watcher_class in components['watchers']:
                    self.watcher_manager.register_watcher(watcher_class)
                    self.logger.info(f"Registered watcher: {watcher_class.__name__}")
                    
                # Log available agents
                for agent_class in components['agents']:
                    self.logger.info(f"Found agent: {agent_class.__name__}")
                    
            except Exception as e:
                self.logger.error(f"Failed to register components for {extension_dir}: {e}")