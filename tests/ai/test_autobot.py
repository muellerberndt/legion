import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from src.ai.autobot import Autobot
from src.actions.registry import ActionRegistry
from src.actions.base import ActionSpec, ActionArgument
import json


@pytest.fixture
def autobot():
    """Create an Autobot instance with mocked dependencies"""
    # Create mock action registry
    mock_registry = MagicMock(spec=ActionRegistry)

    # Create the action spec
    action_spec = ActionSpec(
        name="test_command",
        description="Test command",
        help_text="Test command help text",
        agent_hint="Test command usage hint",
        arguments=[ActionArgument(name="param1", description="Test param", required=True)],
    )

    # Set up the registry mock
    mock_registry._get_agent_command_instructions.return_value = {"test_command": action_spec}
    mock_registry.get_action.return_value = (AsyncMock(return_value="Command result"), action_spec)

    # Create autobot instance
    bot = Autobot(action_registry=mock_registry)
    return bot


@pytest.mark.asyncio
async def test_execute_command_success(autobot):
    """Test successful command execution"""
    result = await autobot.execute_command("test_command", "param1=test")
    assert result == "Command result"


@pytest.mark.asyncio
async def test_execute_command_unknown(autobot):
    """Test executing unknown command"""
    with pytest.raises(ValueError, match="Unknown command: unknown_command"):
        await autobot.execute_command("unknown_command", "")


@pytest.mark.asyncio
async def test_plan_next_step():
    # Create mock action registry with help command
    mock_registry = MagicMock()
    mock_registry._get_agent_command_instructions.return_value = {
        "help": ActionSpec(
            name="help",
            description="Get help about available commands",
            help_text="Usage: /help [command]",
            agent_hint="Use this to get information about commands",
        )
    }

    # Create Autobot instance with mock registry
    autobot = Autobot(action_registry=mock_registry)

    # Mock chat_completion to return a JSON string
    mock_response = json.dumps(
        {"thought": "Test thought", "command": "help", "output": "Test output", "is_final": False}  # Using the mocked command
    )

    with patch("src.ai.autobot.chat_completion", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = mock_response

        # Test planning with empty state
        result = await autobot.plan_next_step({})

        # Result should be parsed JSON
        expected = {"thought": "Test thought", "command": "help", "output": "Test output", "is_final": False}
        assert result == expected
        assert mock_chat.called

        # Verify the messages passed to chat_completion
        call_args = mock_chat.call_args[0][0]
        assert len(call_args) == 3  # System prompt, instructions, and user state
        assert call_args[0]["role"] == "system"
        assert call_args[1]["role"] == "system"
        assert call_args[2]["role"] == "user"


@pytest.mark.asyncio
async def test_execute_task_success(autobot):
    """Test successful task execution"""
    mock_response = json.dumps(
        {"thought": "Test reasoning", "command": "test_command param1=test", "output": "Test output", "is_final": True}
    )

    with patch("src.ai.autobot.chat_completion", AsyncMock(return_value=mock_response)):
        result = await autobot.execute_task({"prompt": "Test prompt"})
        assert result.success is True
        assert result.data["result"] == "Test output"
        assert autobot.state["status"] == "completed"


@pytest.mark.asyncio
async def test_execute_task_max_steps(autobot):
    """Test task execution with max steps limit"""
    mock_response = json.dumps(
        {"thought": "Test reasoning", "command": "test_command param1=test", "output": "Test output", "is_final": False}
    )

    with patch("src.ai.autobot.chat_completion", AsyncMock(return_value=mock_response)):
        autobot.max_steps = 2  # Set low step limit
        result = await autobot.execute_task({"prompt": "Test prompt"})
        assert result.success is False
        assert "exceeded maximum steps" in result.error


@pytest.mark.asyncio
async def test_get_execution_summary(autobot):
    """Test getting execution summary"""
    # Execute a task first to populate execution data
    mock_response = json.dumps({"thought": "Test reasoning", "command": "test_command param1=test", "is_final": True})

    with patch("src.ai.autobot.chat_completion", AsyncMock(return_value=mock_response)):
        await autobot.execute_task({"prompt": "Test prompt"})
        summary = autobot.get_execution_summary()
        assert isinstance(summary, dict)
        assert "execution_id" in summary
        assert "steps_taken" in summary
        assert "status" in summary


@pytest.mark.asyncio
async def test_direct_response(autobot):
    """Test handling of direct responses without commands"""
    mock_response = json.dumps(
        {"thought": "Hello! How can I help you?", "command": "", "output": "Hello! How can I help you?", "is_final": True}
    )

    with patch("src.ai.autobot.chat_completion", AsyncMock(return_value=mock_response)):
        result = await autobot.execute_task({"prompt": "Just say hello"})
        assert result.success is True
        assert result.data["result"] == "Hello! How can I help you?"
        assert autobot.state["status"] == "completed"

        # Verify step was recorded correctly
        summary = autobot.get_execution_summary()
        assert len(summary["steps"]) == 1
        assert summary["steps"][0]["action"] == "response"
        assert summary["steps"][0]["reasoning"] == "Hello! How can I help you?"
