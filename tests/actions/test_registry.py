import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.actions.registry import ActionRegistry
from src.actions.base import BaseAction, ActionSpec
from src.actions.result import ActionResult

# Mock action for testing
class MockAction(BaseAction):
    spec = ActionSpec(
        name="mock_action",
        description="Mock action for testing",
        help_text="Help text",
        agent_hint="Agent hint"
    )
    
    async def execute(self, *args, **kwargs):
        return "Mock result"

class MockActionWithResult(BaseAction):
    spec = ActionSpec(
        name="mock_action_result",
        description="Mock action returning ActionResult",
        help_text="Help text",
        agent_hint="Agent hint"
    )
    
    async def execute(self, *args, **kwargs):
        return ActionResult(content="Mock result")

@pytest.fixture
def action_registry():
    with patch('src.actions.registry.SemanticSearchAction', create=True):
        # Create a fresh registry for each test
        registry = ActionRegistry()
        registry._instance = None
        registry._initialized = False
        return registry

@pytest.fixture
def mock_builtin_actions():
    with patch('src.actions.registry.get_builtin_actions') as mock:
        mock.return_value = [MockAction]
        yield mock

def test_singleton_pattern():
    """Test that ActionRegistry is a singleton"""
    with patch('src.actions.registry.SemanticSearchAction', create=True):
        registry1 = ActionRegistry()
        registry2 = ActionRegistry()
        assert registry1 is registry2

def test_initialization(action_registry, mock_builtin_actions):
    """Test registry initialization with built-in actions"""
    action_registry.initialize()
    
    # Verify built-in actions were registered
    assert "mock_action" in action_registry.actions
    assert len(action_registry.actions) == 1
    assert action_registry._initialized is True

def test_register_action(action_registry):
    """Test registering a custom action"""
    action_registry.register_action("test", MockAction)
    
    assert "test" in action_registry.actions
    handler, spec = action_registry.actions["test"]
    assert spec is MockAction.spec
    assert callable(handler)

@pytest.mark.asyncio
async def test_action_handler(action_registry):
    """Test the created action handler"""
    action_registry.register_action("test", MockAction)
    handler, _ = action_registry.actions["test"]
    
    result = await handler()
    assert result == "Mock result"

@pytest.mark.asyncio
async def test_action_handler_with_result(action_registry):
    """Test handler with ActionResult return type"""
    action_registry.register_action("test", MockActionWithResult)
    handler, _ = action_registry.actions["test"]
    
    result = await handler()
    assert result == "Mock result"

@pytest.mark.asyncio
async def test_action_handler_error(action_registry):
    """Test handler error handling"""
    class ErrorAction(MockAction):
        async def execute(self, *args, **kwargs):
            raise Exception("Test error")
    
    action_registry.register_action("test", ErrorAction)
    handler, _ = action_registry.actions["test"]
    
    with pytest.raises(Exception) as exc:
        await handler()
    assert str(exc.value) == "Test error"

def test_get_action(action_registry, mock_builtin_actions):
    """Test getting an action by name"""
    action_registry.initialize()
    
    # Get existing action
    action = action_registry.get_action("mock_action")
    assert action is not None
    assert action[1] is MockAction.spec
    
    # Get non-existent action
    assert action_registry.get_action("nonexistent") is None

def test_get_actions(action_registry, mock_builtin_actions):
    """Test getting all registered actions"""
    action_registry.initialize()
    
    actions = action_registry.get_actions()
    assert len(actions) == 1
    assert "mock_action" in actions 