import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from src.ai.autobot import Autobot
from src.actions.registry import ActionRegistry
from src.actions.base import ActionSpec, ActionArgument
import json


@pytest.fixture
def mock_action_registry():
    """Fixture for mocked ActionRegistry"""
    registry = MagicMock(spec=ActionRegistry)

    # Mock commands
    commands = {
        "test_command": ActionSpec(
            name="test_command",
            description="Test command",
            help_text="Test help",
            agent_hint="Test hint",
            arguments=[
                ActionArgument(name="param1", description="First parameter", required=True),
            ],
        )
    }

    registry._get_agent_command_instructions.return_value = commands
    registry.get_action.return_value = (AsyncMock(return_value="Command result"), commands["test_command"])
    return registry


@pytest.fixture
def autobot(mock_action_registry):
    """Fixture for Autobot instance"""
    return Autobot(action_registry=mock_action_registry)


@pytest.mark.asyncio
async def test_autobot_initialization(autobot, mock_action_registry):
    """Test Autobot initialization"""
    assert autobot.action_registry == mock_action_registry
    assert "test_command" in autobot.commands
    assert autobot.max_steps == 10
    assert autobot.timeout == 300


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
async def test_plan_next_step(autobot):
    """Test planning next step"""
    mock_response = """
    {
        "reasoning": "Test reasoning",
        "action": "test_command",
        "parameters": "param1=test",
        "is_final": true
    }
    """

    with patch("src.ai.autobot.chat_completion", AsyncMock(return_value=mock_response)) as mock_chat:
        plan = await autobot.plan_next_step({"status": "started"})

        # Verify the plan
        assert plan["reasoning"] == "Test reasoning"
        assert plan["action"] == "test_command"
        assert plan["parameters"] == "param1=test"
        assert plan["is_final"] is True

        # Verify the system prompt includes the correct parameter format
        calls = mock_chat.call_args_list
        assert len(calls) == 1
        messages = calls[0][0][0]  # Get the messages argument
        system_prompt = next(msg["content"] for msg in messages if msg["role"] == "system" and "Parameters:" in msg["content"])
        assert "Parameters: param1*" in system_prompt  # param1 is required so has *


@pytest.mark.asyncio
async def test_execute_task_success(autobot):
    """Test successful task execution"""
    # Mock successful planning and execution
    mock_plan = {"reasoning": "Test reasoning", "action": "test_command", "parameters": "param1=test", "is_final": True}

    with patch("src.ai.autobot.chat_completion", AsyncMock(return_value=json.dumps(mock_plan))):
        result = await autobot.execute_task({"prompt": "Test task"})

        assert result.success is True
        assert result.data is not None
        assert "result" in result.data

        # Check the enhanced result format
        result_data = result.data["result"]
        assert isinstance(result_data, dict)
        assert "final_result" in result_data
        assert "execution_summary" in result_data
        assert result_data["final_result"] == "Command result"

        # Verify execution summary structure
        summary = result_data["execution_summary"]
        assert isinstance(summary, dict)
        assert "execution_id" in summary
        assert "status" in summary
        assert "steps" in summary
        assert len(summary["steps"]) == 1
        assert summary["steps"][0]["action"] == "test_command"
        assert summary["steps"][0]["reasoning"] == "Test reasoning"


@pytest.mark.asyncio
async def test_get_execution_summary(autobot):
    """Test getting execution summary"""
    # Execute a task first
    mock_plan = {"reasoning": "Test reasoning", "action": "test_command", "parameters": "param1=test", "is_final": True}

    with patch("src.ai.autobot.chat_completion", AsyncMock(return_value=json.dumps(mock_plan))):
        result = await autobot.execute_task({"prompt": "Test task"})
        assert result.success is True  # Ensure task succeeded

        summary = autobot.get_execution_summary()
        assert summary["status"] == "completed"
        assert len(summary["steps"]) == 1
        assert summary["steps"][0]["action"] == "test_command"
        assert summary["steps"][0]["reasoning"] == "Test reasoning"


@pytest.mark.asyncio
async def test_execute_task_max_steps(autobot):
    """Test task execution with max steps limit"""
    # Mock plan that doesn't set is_final to true
    mock_plan = {"reasoning": "Test reasoning", "action": "test_command", "parameters": "param1=test", "is_final": False}

    with patch("src.ai.autobot.chat_completion", AsyncMock(return_value=json.dumps(mock_plan))):
        result = await autobot.execute_task({"prompt": "Test task"})

        assert result.success is False
        assert "exceeded maximum steps" in result.error
        assert autobot.step_count == autobot.max_steps
