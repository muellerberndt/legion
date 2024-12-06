import importlib
import os
import sys
from typing import Dict, Type
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
        
    def _find_extension_modules(self, extensions_dir: str, active_extensions: list) -> Dict[str, str]:
        """Find extension modules in subdirectories.
        
        Args:
            extensions_dir: Base extensions directory
            active_extensions: List of active extension names
            
        Returns:
            Dict mapping extension names to their module paths
        """
        extension_modules = {}
        
        # Walk through extensions directory
        for root, dirs, files in os.walk(extensions_dir):
            # Skip if this is the root extensions dir
            if root == extensions_dir:
                continue
                
            # Get relative path from extensions dir
            rel_path = os.path.relpath(root, extensions_dir)
            extension_name = os.path.basename(root)
            
            # Skip if not in active extensions
            if extension_name not in active_extensions:
                continue
                
            # Look for Python files
            for file in files:
                if file.endswith('.py') and not file.startswith('_'):
                    # Convert path to module notation
                    module_path = f"extensions.{rel_path.replace(os.sep, '.')}.{file[:-3]}"
                    extension_modules[extension_name] = module_path
                    break
                    
        return extension_modules
        
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
            
        # Find extension modules
        extension_modules = self._find_extension_modules(extensions_dir, active_extensions)
            
        for extension_name, module_path in extension_modules.items():
            try:
                # Load extension config first
                config_path = os.path.join(extensions_dir, extension_name, "extra_config.yml")
                if os.path.exists(config_path):
                    self.config.load_extension_config(config_path)
                
                # Import the extension module
                module = importlib.import_module(module_path)
                
                # Collect components
                actions = {}
                handlers = []
                watchers = []
                agents = []
                
                # Look for components in the module's __all__
                if hasattr(module, '__all__'):
                    for item_name in module.__all__:
                        item = getattr(module, item_name)
                        if isinstance(item, type):
                            if issubclass(item, BaseAction) and item != BaseAction:
                                actions[item.spec.name] = item
                            elif issubclass(item, Handler) and item != Handler:
                                handlers.append(item)
                            elif issubclass(item, WatcherJob) and item != WatcherJob:
                                watchers.append(item)
                            elif issubclass(item, BaseAgent) and item != BaseAgent:
                                agents.append(item)
                                
                self.extensions[extension_name] = {
                    'actions': actions,
                    'handlers': handlers,
                    'watchers': watchers,
                    'agents': agents
                }
                
                self.logger.info(f"Loaded extension: {extension_name}")
                self.logger.info(f"Found components: {len(actions)} actions, {len(handlers)} handlers, {len(watchers)} watchers, {len(agents)} agents")
                
            except Exception as e:
                self.logger.error(f"Failed to load extension {extension_name}: {e}")
                
    def register_components(self) -> None:
        """Register all components from loaded extensions"""
        for extension_name, components in self.extensions.items():
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
                self.logger.error(f"Failed to register components for {extension_name}: {e}")