import importlib
import os
import sys
from src.actions.base import BaseAction
from src.handlers.base import Handler
from src.util.logging import Logger
from src.actions.registry import ActionRegistry
from src.handlers.registry import HandlerRegistry
from src.config.config import Config
from src.webhooks.handlers import WebhookHandler
from src.webhooks.server import WebhookServer


class ExtensionLoader:
    """Loads and registers extensions"""

    def __init__(self):
        self.logger = Logger("ExtensionLoader")
        self.config = Config()
        self.action_registry = ActionRegistry()
        self.handler_registry = HandlerRegistry()

    def load_extensions(self) -> None:
        """Load all enabled extensions"""
        extensions_dir = self.config.get("extensions_dir", "./extensions")
        active_extensions = self.config.get("active_extensions", [])

        if not active_extensions:
            self.logger.info("No extensions enabled")
            return

        self.logger.info(f"Loading extensions from {extensions_dir}: {active_extensions}")

        for extension in active_extensions:
            try:
                self._load_extension(extensions_dir, extension)
            except Exception as e:
                self.logger.error(f"Failed to load extension {extension}: {str(e)}")

    def _load_extension(self, base_dir: str, extension_path: str) -> None:
        """Load a single extension"""
        # Convert dot notation to path
        path_parts = extension_path.split(".")
        rel_path = os.path.join(*path_parts)
        abs_path = os.path.join(base_dir, rel_path)

        self.logger.info(f"Loading extension from {abs_path}")

        # If path is a directory, load all .py files
        if os.path.isdir(abs_path):
            for file in os.listdir(abs_path):
                if file.endswith(".py") and not file.startswith("_"):
                    self._load_module(os.path.join(abs_path, file))
        else:
            # Load single file
            py_path = f"{abs_path}.py"
            if os.path.exists(py_path):
                self._load_module(py_path)
            else:
                self.logger.warning(f"Extension file not found: {py_path}")

    def _load_module(self, file_path: str) -> None:
        """Load a Python module from file"""
        try:
            # Get module name from file path
            module_name = os.path.splitext(os.path.basename(file_path))[0]

            # Load module
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if not spec or not spec.loader:
                raise ImportError(f"Failed to load spec for {file_path}")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            self.logger.info(f"Loaded module: {module_name}")

        except Exception as e:
            self.logger.error(f"Failed to load module {file_path}: {str(e)}")
            raise

    async def register_components(self) -> None:
        """Register all components found in loaded modules"""
        # Get all loaded classes
        for module_name, module in list(sys.modules.items()):
            if not module_name.startswith("extensions."):
                continue

            self.logger.debug(f"Checking module {module_name} for components")

            try:
                # Register actions
                for item_name in dir(module):
                    item = getattr(module, item_name)
                    if isinstance(item, type):
                        if issubclass(item, BaseAction) and item != BaseAction:
                            self.action_registry.register_action(item.spec.name, item)
                            self.logger.info(f"Registered action: {item.spec.name}")
                        elif issubclass(item, Handler) and item != Handler:
                            self.handler_registry.register_handler(item)
                            self.logger.info(f"Registered handler: {item.__name__}")
                        elif issubclass(item, WebhookHandler) and item != WebhookHandler:
                            webhook_server = await WebhookServer.get_instance()
                            webhook_server.register_handler(f"/{item_name.lower()}", item())
                            self.logger.info(f"Registered webhook handler: {item.__name__}")

            except Exception as e:
                self.logger.error(f"Error registering components from {module_name}: {str(e)}")
                continue
