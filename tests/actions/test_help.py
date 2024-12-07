import pytest
from unittest.mock import Mock, patch
from src.actions.help import HelpAction
from src.actions.registry import ActionRegistry
from src.actions.base import ActionSpec, ActionArgument


@pytest.fixture
def mock_registry():
    registry = Mock(spec=ActionRegistry)
    action_spec = ActionSpec(
        name="test_action",
        description="Test action description",
        help_text="""Test action help text.

Usage:
/test_action <arg1> [arg2]

This command demonstrates the help format.
It shows how arguments are documented.

Examples:
/test_action required optional
/test_action value""",
        agent_hint="Use this action when you need to test something or demonstrate help formatting",
        arguments=[
            ActionArgument(name="arg1", description="First argument", required=True),
            ActionArgument(name="arg2", description="Second argument", required=False),
        ],
    )

    actions = {"test_action": (Mock(), action_spec)}

    registry.get_actions.return_value = actions
    registry.get_action.side_effect = lambda name: actions.get(name)
    return registry


@pytest.mark.asyncio
async def test_help_action_no_args(mock_registry):
    """Test help action without arguments (should list all actions)"""
    with patch("src.actions.registry.ActionRegistry", return_value=mock_registry):
        action = HelpAction()
        result = await action.execute()

        # Verify help text contains action info
        assert "Available Commands:" in result
        assert "test_action" in result
        assert "Test action description" in result
        assert "Test action help text" not in result  # Should not include detailed help


@pytest.mark.asyncio
async def test_help_action_with_command(mock_registry):
    """Test help action with specific command"""
    with patch("src.actions.registry.ActionRegistry", return_value=mock_registry):
        action = HelpAction()
        result = await action.execute("test_action")

        # Verify help text contains detailed command info
        assert "test_action" in result
        assert "Test action help text" in result
        assert "Usage:" in result
        assert "Arguments:" in result
        assert "arg1" in result
        assert "First argument" in result
        assert "(required)" in result
        assert "arg2" in result
        assert "Second argument" in result


@pytest.mark.asyncio
async def test_help_action_unknown_command(mock_registry):
    """Test help action with unknown command"""
    with patch("src.actions.registry.ActionRegistry", return_value=mock_registry):
        action = HelpAction()
        result = await action.execute("unknown_action")

        # Verify error message
        assert "Command 'unknown_action' not found" in result
