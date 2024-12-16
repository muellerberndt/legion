import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import json
from src.ai.chatbot import Chatbot
from src.actions.registry import ActionRegistry
from src.actions.base import ActionSpec, ActionArgument


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
        ),
        "db_query": ActionSpec(
            name="db_query",
            description="Database query",
            help_text="Query the database",
            agent_hint="Use for database queries",
            arguments=[
                ActionArgument(name="query", description="Query to execute", required=True),
            ],
        ),
    }

    registry._get_agent_command_instructions.return_value = commands

    # Mock action handlers
    test_handler = AsyncMock(return_value="Command result")
    db_handler = AsyncMock(return_value={"results": [{"id": 1, "name": "test"}]})

    registry.get_action.side_effect = lambda name: {
        "test_command": (test_handler, commands["test_command"]),
        "db_query": (db_handler, commands["db_query"]),
    }.get(name)

    return registry


@pytest.fixture
def chatbot(mock_action_registry):
    """Fixture for Chatbot instance"""
    with patch("src.ai.chatbot.ActionRegistry", return_value=mock_action_registry):
        return Chatbot()


@pytest.mark.asyncio
async def test_chatbot_initialization(chatbot, mock_action_registry):
    """Test Chatbot initialization"""
    assert chatbot.action_registry == mock_action_registry
    assert len(chatbot.history) == 1  # System message
    assert chatbot.max_history == 10


@pytest.mark.asyncio
async def test_execute_command_success(chatbot):
    """Test successful command execution"""
    result = await chatbot.execute_command("test_command", "param1=test")
    assert result == "Command result"


@pytest.mark.asyncio
async def test_execute_command_db_query(chatbot):
    """Test executing db_query command"""
    query = json.dumps({"collection": "test", "filter": {}, "limit": 10})
    result = await chatbot.execute_command("db_query", f"query={query}")
    assert isinstance(result, dict)
    assert "results" in result


@pytest.mark.asyncio
async def test_execute_command_unknown(chatbot):
    """Test executing unknown command"""
    with pytest.raises(ValueError, match="Unknown command: unknown_command"):
        await chatbot.execute_command("unknown_command", "")


@pytest.mark.asyncio
async def test_format_response():
    """Test response formatting"""
    with patch("src.ai.chatbot.ActionRegistry"):
        chatbot = Chatbot()

        # Test JSON formatting
        json_data = {"key": "value", "nested": {"data": "test"}}
        formatted = chatbot._format_response(json.dumps(json_data))
        assert "key" in formatted
        assert "value" in formatted
        assert "nested" in formatted

        # Test HTML escaping
        html_text = "<script>alert('test')</script>"
        formatted = chatbot._format_response(html_text)
        assert "<script>" not in formatted
        assert "&lt;script&gt;" in formatted


@pytest.mark.asyncio
async def test_add_to_history():
    """Test conversation history management"""
    chatbot = Chatbot()

    # Add messages up to max_history + 2
    for i in range(chatbot.max_history + 2):
        chatbot._add_to_history("user", f"Message {i}")

    # Check that history is trimmed correctly
    assert len(chatbot.history) == chatbot.max_history + 1  # +1 for system message
    assert chatbot.history[0]["role"] == "system"  # System message preserved
    assert chatbot.history[-1]["content"] == f"Message {chatbot.max_history + 1}"  # Latest message preserved


@pytest.mark.asyncio
async def test_process_message(chatbot):
    """Test message processing"""
    # Mock chat completion responses
    responses = [
        "EXECUTE: test_command param1=test",  # First response to determine action
        "Command executed successfully",  # Second response to format result
    ]
    chat_completion_mock = AsyncMock(side_effect=responses)

    with patch("src.ai.chatbot.chat_completion", chat_completion_mock):
        result = await chatbot.process_message("Run test command")

        # Verify message was added to history
        assert len(chatbot.history) == 3  # System + user + assistant
        assert chatbot.history[-2]["role"] == "user"
        assert chatbot.history[-1]["role"] == "assistant"

        # Verify command was executed and result was formatted
        assert "Command executed successfully" in result
