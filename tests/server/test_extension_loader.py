import pytest
from unittest.mock import Mock, patch, MagicMock
from src.server.extension_loader import ExtensionLoader
from src.handlers.base import Handler, HandlerTrigger
from src.actions.base import BaseAction, ActionSpec
from src.jobs.watcher import WatcherJob
from src.agents.base_agent import BaseAgent


# Mock components for testing
class MockHandler(Handler):
    @classmethod
    def get_triggers(cls):
        return [HandlerTrigger.NEW_PROJECT]

    async def handle(self):
        pass


class MockAction(BaseAction):
    spec = ActionSpec(
        name="mock_action", description="Mock action for testing", help_text="Help text", agent_hint="Agent hint"
    )

    async def execute(self):
        pass


class MockWatcher(WatcherJob):
    async def start(self):
        pass

    async def stop(self):
        pass


class MockAgent(BaseAgent):
    pass


@pytest.fixture
def extension_loader():
    with (
        patch("src.server.extension_loader.Config") as mock_config,
        patch("src.server.extension_loader.ActionRegistry") as mock_action_registry,
        patch("src.server.extension_loader.HandlerRegistry") as mock_handler_registry,
        patch("src.server.extension_loader.WatcherManager") as mock_watcher_manager,
    ):
        # Mock config to return test values
        config_instance = mock_config.return_value
        config_instance.get.side_effect = lambda key, default=None: {
            "extensions_dir": "/test/extensions",
            "active_extensions": ["test_extension"],
        }.get(key, default)

        # Create mock registries
        action_registry = mock_action_registry.return_value
        handler_registry = Mock()
        watcher_manager = Mock()

        # Set up mock methods
        action_registry.register_action = Mock()
        handler_registry.register_handler = Mock()
        watcher_manager.register_watcher = Mock()

        # Set up singleton mocks
        mock_handler_registry.get_instance.return_value = handler_registry
        mock_watcher_manager.get_instance.return_value = watcher_manager

        loader = ExtensionLoader()
        loader.action_registry = action_registry
        loader.handler_registry = handler_registry
        loader.watcher_manager = watcher_manager

        return loader


@pytest.fixture
def mock_module():
    module = MagicMock()
    module.__name__ = "test_module"

    # Add our mock components to the module
    MockHandler.__module__ = "test_module"
    MockAction.__module__ = "test_module"
    MockWatcher.__module__ = "test_module"
    MockAgent.__module__ = "test_module"

    module.MockHandler = MockHandler
    module.MockAction = MockAction
    module.MockWatcher = MockWatcher
    module.MockAgent = MockAgent

    return module


def test_discover_components(extension_loader, mock_module):
    """Test component discovery from a module"""
    components = extension_loader._discover_components(mock_module)

    # Verify components were discovered correctly
    assert "mock_action" in components["actions"]
    assert len(components["handlers"]) == 1
    assert len(components["watchers"]) == 1
    assert len(components["agents"]) == 1

    # Verify correct classes were found
    assert components["actions"]["mock_action"] == MockAction
    assert components["handlers"][0] == MockHandler
    assert components["watchers"][0] == MockWatcher
    assert components["agents"][0] == MockAgent


@patch("builtins.open", create=True)
@patch("importlib.import_module")
@patch("os.path.exists")
@patch("os.walk")
def test_load_extensions(mock_walk, mock_exists, mock_import, mock_open, extension_loader):
    """Test loading extensions from files"""
    # Setup mocks
    mock_exists.return_value = True
    mock_walk.return_value = [("/test/extensions/test_extension", [], ["test_components.py"])]

    # Create a mock module with our test content
    mock_module = MagicMock()
    mock_module.__name__ = "test_extension.test_components"

    # Add test components to the module
    class TestHandler(Handler):
        @classmethod
        def get_triggers(cls):
            return [HandlerTrigger.NEW_PROJECT]

        async def handle(self):
            pass

    class TestAction(BaseAction):
        spec = ActionSpec(name="test_action", description="Test action", help_text="Help", agent_hint="Hint")

        async def execute(self):
            pass

    # Set the module name for the test classes
    TestHandler.__module__ = mock_module.__name__
    TestAction.__module__ = mock_module.__name__

    mock_module.TestHandler = TestHandler
    mock_module.TestAction = TestAction
    mock_import.return_value = mock_module

    # Mock file reading
    mock_open.return_value.__enter__.return_value.read.return_value = ""

    # Load extensions
    extension_loader.load_extensions()

    # Verify components were discovered
    assert "test_extension" in extension_loader.extensions
    components = extension_loader.extensions["test_extension"]
    assert len(components["handlers"]) == 1
    assert len(components["actions"]) == 1
    assert components["handlers"][0] == TestHandler
    assert components["actions"]["test_action"] == TestAction


def test_register_components(extension_loader):
    """Test registering discovered components"""
    # Setup test data
    extension_loader.extensions = {
        "test_extension": {
            "actions": {"mock_action": MockAction},
            "handlers": [MockHandler],
            "watchers": [MockWatcher],
            "agents": [MockAgent],
        }
    }

    # Register components
    extension_loader.register_components()

    # Verify registrations
    extension_loader.action_registry.register_action.assert_called_once_with("mock_action", MockAction)
    extension_loader.handler_registry.register_handler.assert_called_once_with(MockHandler)
    extension_loader.watcher_manager.register_watcher.assert_called_once_with(MockWatcher)


def test_discover_components_imported_classes(extension_loader):
    """Test that imported classes are not discovered"""
    module = MagicMock()
    module.__name__ = "test_module"

    # Create a class that looks like it's imported (different module name)
    imported_action = type(
        "ImportedAction",
        (BaseAction,),
        {
            "__module__": "different_module",
            "spec": ActionSpec(name="imported_action", description="Imported action", help_text="Help", agent_hint="Hint"),
        },
    )
    module.ImportedAction = imported_action

    components = extension_loader._discover_components(module)
    assert len(components["actions"]) == 0  # Should not discover imported class


def test_discover_components_base_classes(extension_loader):
    """Test that base classes are not discovered"""
    module = MagicMock()
    module.__name__ = "test_module"

    # Add base classes to module
    module.BaseAction = BaseAction
    module.Handler = Handler
    module.WatcherJob = WatcherJob
    module.BaseAgent = BaseAgent

    components = extension_loader._discover_components(module)
    assert len(components["actions"]) == 0
    assert len(components["handlers"]) == 0
    assert len(components["watchers"]) == 0
    assert len(components["agents"]) == 0


def test_load_extensions_nonexistent_directory(extension_loader):
    """Test loading extensions from a nonexistent directory"""
    with patch("os.path.exists", return_value=False):
        extension_loader.load_extensions()
        assert len(extension_loader.extensions) == 0


def test_load_extensions_empty_directory(extension_loader):
    """Test loading extensions from an empty directory"""
    with (
        patch("os.path.exists", return_value=True),
        patch("os.walk", return_value=[]),
        patch.object(
            extension_loader.config,
            "get",
            side_effect=lambda key, default=None: {
                "extensions_dir": "/test/extensions",
                "active_extensions": [],  # Empty list of active extensions
            }.get(key, default),
        ),
    ):
        extension_loader.load_extensions()
        assert len(extension_loader.extensions) == 0


def test_load_extensions_with_extra_config(extension_loader):
    """Test loading extensions with extra configuration"""
    with (
        patch("os.path.exists", side_effect=lambda p: True),
        patch("os.walk", return_value=[("/test/extensions/test_extension", [], ["test_components.py"])]),
        patch("importlib.import_module", return_value=MagicMock()),
    ):
        extension_loader.load_extensions()
        extension_loader.config.load_extension_config.assert_called_once()


def test_find_python_modules(extension_loader):
    """Test finding Python modules in a directory"""
    mock_walk_data = [
        ("/test/extensions/test_extension", [], ["test_file.py", "_ignored.py", "not_python.txt"]),
        ("/test/extensions/test_extension/subdir", [], ["sub_module.py"]),
    ]

    with (
        patch("os.walk", return_value=mock_walk_data),
        patch.object(extension_loader.config, "get", return_value="/test/extensions"),
    ):
        modules = extension_loader._find_python_modules("/test/extensions/test_extension")
        assert "test_extension.test_file" in modules
        assert "test_extension.subdir.sub_module" in modules
        assert "_ignored" not in modules
        assert "not_python" not in modules
