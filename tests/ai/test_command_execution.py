import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from src.ai.chatbot import Chatbot
from src.ai.autobot import Autobot
from src.actions.registry import ActionRegistry
from src.actions.base import ActionSpec, ActionArgument


@pytest.fixture
def chatbot():
    """Create a chatbot instance for testing"""
    chatbot = Chatbot()
    chatbot.action_registry = MagicMock(spec=ActionRegistry)

    # Add test commands
    chatbot.commands = {
        "no_params": ActionSpec(
            name="no_params",
            description="Command with no parameters",
            help_text="Test help",
            agent_hint="Test hint",
            arguments=[],
        ),
        "required_params": ActionSpec(
            name="required_params",
            description="Command with required parameters",
            help_text="Test help",
            agent_hint="Test hint",
            arguments=[
                ActionArgument(name="param1", description="First parameter", required=True),
                ActionArgument(name="param2", description="Second parameter", required=True),
            ],
        ),
        "optional_params": ActionSpec(
            name="optional_params",
            description="Command with optional parameters",
            help_text="Test help",
            agent_hint="Test hint",
            arguments=[
                ActionArgument(name="opt1", description="Optional parameter", required=False),
            ],
        ),
        "mixed_params": ActionSpec(
            name="mixed_params",
            description="Command with mixed parameters",
            help_text="Test help",
            agent_hint="Test hint",
            arguments=[
                ActionArgument(name="required", description="Required parameter", required=True),
                ActionArgument(name="optional", description="Optional parameter", required=False),
            ],
        ),
        "job": ActionSpec(
            name="job",
            description="Get job results",
            help_text="Test help",
            agent_hint="Test hint",
            arguments=[
                ActionArgument(name="job_id", description="Job ID", required=False),
            ],
        ),
    }

    # Mock handlers
    no_params_handler = AsyncMock(return_value="No params result")
    required_params_handler = AsyncMock(return_value="Required params result")
    optional_params_handler = AsyncMock(return_value="Optional params result")
    mixed_params_handler = AsyncMock(return_value="Mixed params result")
    job_handler = AsyncMock(return_value="Job result")

    # Configure action registry
    chatbot.action_registry.get_action.side_effect = lambda name: {
        "no_params": (no_params_handler, chatbot.commands["no_params"]),
        "required_params": (required_params_handler, chatbot.commands["required_params"]),
        "optional_params": (optional_params_handler, chatbot.commands["optional_params"]),
        "mixed_params": (mixed_params_handler, chatbot.commands["mixed_params"]),
        "job": (job_handler, chatbot.commands["job"]),
    }.get(name)

    return chatbot


class TestChatbotCommandExecution:
    """Test Chatbot command execution functionality"""

    @pytest.mark.asyncio
    async def test_no_params_command(self, chatbot):
        """Test executing command with no parameters"""
        result = await chatbot.execute_command("no_params", "")
        assert result == "No params result"

    @pytest.mark.asyncio
    async def test_required_params_command(self, chatbot):
        """Test executing command with required parameters"""
        result = await chatbot.execute_command("required_params", "param1=value1 param2=value2")
        assert result == "Required params result"

    @pytest.mark.asyncio
    async def test_optional_params_command(self, chatbot):
        """Test executing command with optional parameters"""
        # Test with no parameters
        result = await chatbot.execute_command("optional_params", "")
        assert result == "Optional params result"

        # Test with some optional parameters
        result = await chatbot.execute_command("optional_params", "opt1=value1")
        assert result == "Optional params result"

    @pytest.mark.asyncio
    async def test_mixed_params_command(self, chatbot):
        """Test executing command with mixed parameters"""
        # Test with only required parameter
        result = await chatbot.execute_command("mixed_params", "required=value1")
        assert result == "Mixed params result"

        # Test with both parameters
        result = await chatbot.execute_command("mixed_params", "required=value1 optional=value2")
        assert result == "Mixed params result"

    @pytest.mark.asyncio
    async def test_quoted_parameters(self, chatbot):
        """Test handling of quoted parameters"""
        # Test with single quotes
        result = await chatbot.execute_command("required_params", "param1='value 1' param2='value 2'")
        assert result == "Required params result"

        # Test with double quotes
        result = await chatbot.execute_command("required_params", 'param1="value 1" param2="value 2"')
        assert result == "Required params result"
