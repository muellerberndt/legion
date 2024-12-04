import pytest
from unittest.mock import Mock, patch
from src.actions.help import HelpAction
from src.actions.registry import ActionRegistry
from src.actions.base import ActionSpec, ActionArgument
from src.actions.result import ActionResult

@pytest.fixture
def mock_registry():
    registry = Mock(spec=ActionRegistry)
    registry.get_actions.return_value = {
        'test_action': (
            Mock(),
            ActionSpec(
                name="test_action",
                description="Test action description",
                arguments=[
                    ActionArgument(name="arg1", description="First argument", required=True),
                    ActionArgument(name="arg2", description="Second argument", required=False)
                ]
            )
        )
    }
    return registry

@pytest.mark.asyncio
async def test_help_action_no_args(mock_registry):
    """Test help action without arguments (should list all actions)"""
    with patch('src.actions.registry.ActionRegistry', return_value=mock_registry):
        action = HelpAction()
        result = await action.execute()
        
        # Verify help text contains action info
        assert isinstance(result, ActionResult)
        assert "Available Commands:" in result.content
        assert "test_action" in result.content
        assert "Test action description" in result.content

@pytest.mark.asyncio
async def test_help_action_with_command(mock_registry):
    """Test help action with specific command"""
    with patch('src.actions.registry.ActionRegistry', return_value=mock_registry):
        action = HelpAction()
        result = await action.execute("test_action")
        
        # Verify help text contains detailed command info
        assert isinstance(result, ActionResult)
        assert "test_action" in result.content
        assert "Test action description" in result.content
        assert "Arguments:" in result.content
        assert "arg1" in result.content
        assert "First argument" in result.content
        assert "(required)" in result.content
        assert "arg2" in result.content
        assert "Second argument" in result.content

@pytest.mark.asyncio
async def test_help_action_unknown_command(mock_registry):
    """Test help action with unknown command"""
    with patch('src.actions.registry.ActionRegistry', return_value=mock_registry):
        action = HelpAction()
        result = await action.execute("unknown_action")
        
        # Verify error message
        assert isinstance(result, ActionResult)
        assert "Command not found" in result.content 