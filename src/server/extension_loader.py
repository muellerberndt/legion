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

class ExtensionLoader:
    """Loads and manages extensions"""
    
    def __init__(self):
        self.logger = Logger("ExtensionLoader")
        self.extensions = {}
        self.action_registry = ActionRegistry()
        self.handler_registry = HandlerRegistry()
        self.watcher_manager = WatcherManager()
        
    def load_extensions(self) -> None:
        """Load all extensions from the extensions directory"""
        extensions_dir = "extensions"
        if not os.path.exists(extensions_dir):
            return
            
        for filename in os.listdir(extensions_dir):
            if filename.endswith('.py') and not filename.startswith('_'):
                extension_name = filename[:-3]  # Remove .py
                try:
                    module = importlib.import_module(f"extensions.{extension_name}")
                    
                    # Collect components
                    actions = {}
                    handlers = []
                    watchers = []
                    
                    for item_name in dir(module):
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
                    
                except Exception as e:
                    self.logger.error(f"Failed to load extension {extension_name}: {e}")
                    
    def register_components(self) -> None:
        """Register all components from loaded extensions"""
        for extension_name, components in self.extensions.items():
            try:
                # Register actions
                for name, action_class in components['actions'].items():
                    self.action_registry.register_action(name, action_class)
                    
                # Register handlers
                for handler_class in components['handlers']:
                    self.handler_registry.register_handler(handler_class)
                    
                # Register watchers
                for watcher_class in components['watchers']:
                    self.watcher_manager.register_watcher(watcher_class)
                    
            except Exception as e:
                self.logger.error(f"Failed to register components for {extension_name}: {e}")