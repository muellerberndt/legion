import sys
import pytest
from unittest.mock import Mock, patch, AsyncMock, ANY
from src.server.extension_loader import ExtensionLoader
from src.actions.base import BaseAction, ActionSpec
from src.handlers.base import Handler
from src.webhooks.handlers import WebhookHandler
import importlib.util


class MockAction(BaseAction):
    """Mock action for testing"""

    spec = ActionSpec(
        name="mock_action",
        description="Mock action for testing",
        help_text="Mock help text",
        agent_hint="Mock agent hint",
        arguments=[],
    )

    async def execute(self, *args, **kwargs):
        return "Mock result"


class MockHandler(Handler):
    """Mock handler for testing"""

    @classmethod
    def get_triggers(cls):
        return []

    async def handle(self):
        pass


class MockWebhookHandler(WebhookHandler):
    """Mock webhook handler for testing"""

    async def handle(self, request):
        return "Mock webhook response"


@pytest.fixture
def extension_loader():
    """Create extension loader with mocked dependencies"""
    loader = ExtensionLoader()
    loader.action_registry.register_action = Mock()
    loader.handler_registry.register_handler = Mock()
    return loader


@pytest.fixture
def mock_webhook_server():
    """Create mock webhook server"""
    server = Mock()
    server.register_handler = Mock()
    return server


@pytest.mark.asyncio
async def test_register_components(extension_loader, mock_webhook_server):
    """Test registering components from a module"""
    # Create mock module with components
    mock_module = Mock()
    mock_module.__name__ = "extensions.test"
    mock_module.MockAction = MockAction
    mock_module.MockHandler = MockHandler
    mock_module.MockWebhookHandler = MockWebhookHandler

    # Mock sys.modules while preserving existing modules
    mock_modules = dict(sys.modules)
    mock_modules["extensions.test"] = mock_module

    with (
        patch.dict("sys.modules", mock_modules),
        patch("src.webhooks.server.WebhookServer.get_instance", return_value=mock_webhook_server),
    ):

        await extension_loader.register_components()

        # Verify action was registered
        extension_loader.action_registry.register_action.assert_called_with("mock_action", MockAction)

        # Verify handler was registered
        extension_loader.handler_registry.register_handler.assert_called_with(MockHandler)

        # Verify webhook handler was registered
        mock_webhook_server.register_handler.assert_called_with(
            "/mockwebhookhandler", ANY  # Use ANY to match any handler instance
        )


def test_load_extensions(extension_loader, tmp_path):
    """Test loading extensions from directory"""
    # Create test extension file
    ext_dir = tmp_path / "extensions"
    ext_dir.mkdir()
    test_ext = ext_dir / "test_ext.py"
    test_ext.write_text(
        """
from src.actions.base import BaseAction, ActionSpec

class TestAction(BaseAction):
    spec = ActionSpec(
        name="test_action",
        description="Test action",
        help_text="Test help",
        agent_hint="Test hint",
        arguments=[],
    )

    async def execute(self, *args, **kwargs):
        return "Test result"
    """
    )

    # Mock config
    extension_loader.config.get = Mock(
        side_effect=lambda key, default: {
            "extensions_dir": str(ext_dir),
            "active_extensions": ["test_ext"],
        }[key]
    )

    # Mock module loading
    with (
        patch("importlib.util.spec_from_file_location") as mock_spec_from_file_location,
        patch("importlib.util.module_from_spec") as mock_module_from_spec,
    ):

        # Create mock module
        mock_module = Mock()
        mock_module.__name__ = "test_ext"

        # Set up the mock spec
        mock_spec = Mock()
        mock_spec.loader = Mock()
        mock_spec.loader.exec_module = Mock()
        mock_spec_from_file_location.return_value = mock_spec
        mock_module_from_spec.return_value = mock_module

        # Load extensions
        extension_loader.load_extensions()

        # Verify module loading was attempted
        mock_spec_from_file_location.assert_called_once()
        mock_module_from_spec.assert_called_once()
        mock_spec.loader.exec_module.assert_called_once_with(mock_module)
