import importlib
import os
from typing import Dict, Type
from src.actions.base import BaseAction
from src.handlers.base import Handler
from src.jobs.watcher import WatcherJob
from src.util.logging import Logger
from src.actions.registry import ActionRegistry
from src.handlers.registry import HandlerRegistry
from src.watchers.manager import WatcherManager
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
        
    def load_extensions(self) -> None:
        """Load all extensions from the extensions directory"""
        extensions_dir = self.config.get("extensions_dir", "extensions")
        active_extensions = self.config.get("active_extensions", [])
        
        if not os.path.exists(extensions_dir):
            self.logger.info(f"Extensions directory {extensions_dir} not found")
            return
            
        self.logger.info(f"Loading extensions from {extensions_dir}")
        self.logger.info(f"Active extensions: {active_extensions}")
            
        for extension_name in active_extensions:
            try:
                # Import the extension package
                module = importlib.import_module(f"extensions.{extension_name}")
                
                # Collect components
                actions = {}
                handlers = []
                watchers = []
                
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
                                
                self.extensions[extension_name] = {
                    'actions': actions,
                    'handlers': handlers,
                    'watchers': watchers
                }
                
                self.logger.info(f"Loaded extension: {extension_name}")
                self.logger.info(f"Found components: {len(actions)} actions, {len(handlers)} handlers, {len(watchers)} watchers")
                
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
                    
            except Exception as e:
                self.logger.error(f"Failed to register components for {extension_name}: {e}")