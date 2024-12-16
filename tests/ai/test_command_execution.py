import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from src.ai.chatbot import Chatbot
from src.ai.autobot import Autobot
from src.actions.registry import ActionRegistry
from src.actions.base import ActionSpec, ActionArgument
import json


@pytest.fixture
def mock_action_registry():
    """Fixture for mocked ActionRegistry with various test commands"""
    registry = MagicMock(spec=ActionRegistry)

    # Mock commands with different parameter configurations
    action_specs = {
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
                ActionArgument(name="opt1", description="First optional parameter", required=False),
                ActionArgument(name="opt2", description="Second optional parameter", required=False),
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
        "db_query": ActionSpec(
            name="db_query",
            description="Database query",
            help_text="Query the database",
            agent_hint="Use for database queries",
            arguments=[
                ActionArgument(name="query", description="Query to execute", required=True),
            ],
        ),
        "job_command": ActionSpec(
            name="job_command",
            description="Command that returns a job",
            help_text="Test help",
            agent_hint="Test hint",
            arguments=[
                ActionArgument(name="param1", description="First parameter", required=True),
            ],
        ),
    }

    # Set up registry mocks
    registry._get_agent_command_instructions.return_value = action_specs

    # Mock action handlers with their specs
    handlers = {
        "no_params": (AsyncMock(return_value="No params result"), action_specs["no_params"]),
        "required_params": (AsyncMock(return_value="Required params result"), action_specs["required_params"]),
        "optional_params": (AsyncMock(return_value="Optional params result"), action_specs["optional_params"]),
        "mixed_params": (AsyncMock(return_value="Mixed params result"), action_specs["mixed_params"]),
        "db_query": (AsyncMock(return_value={"results": [{"id": 1}]}), action_specs["db_query"]),
        "job_command": (AsyncMock(return_value="Job started with ID: job_123"), action_specs["job_command"]),
    }

    registry.get_action.side_effect = lambda name: handlers.get(name)
    return registry


@pytest.fixture
def chatbot(mock_action_registry):
    """Fixture for Chatbot instance"""
    with patch("src.ai.chatbot.ActionRegistry", return_value=mock_action_registry):
        return Chatbot()


@pytest.fixture
def autobot(mock_action_registry):
    """Fixture for Autobot instance"""
    return Autobot(action_registry=mock_action_registry)


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
        # Test with keyword arguments
        result = await chatbot.execute_command("required_params", "param1=value1 param2=value2")
        assert result == "Required params result"

        # Test with positional arguments
        result = await chatbot.execute_command("required_params", "value1 value2")
        assert result == "Required params result"

        # Test with missing parameters - should raise ValueError
        with pytest.raises(ValueError, match="Missing required parameters"):
            await chatbot.execute_command("required_params", "param1=value1")

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

        # Test with both required and optional parameters
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


class TestAutobotCommandExecution:
    """Test Autobot command execution functionality"""

    @pytest.mark.asyncio
    async def test_no_params_command(self, autobot):
        """Test executing command with no parameters"""
        result = await autobot.execute_command("no_params", "")
        assert result == "No params result"

    @pytest.mark.asyncio
    async def test_required_params_command(self, autobot):
        """Test executing command with required parameters"""
        # Test with keyword arguments
        result = await autobot.execute_command("required_params", "param1=value1 param2=value2")
        assert result == "Required params result"

        # Test with positional arguments
        result = await autobot.execute_command("required_params", "value1 value2")
        assert result == "Required params result"

        # Test with missing parameters - should raise ValueError
        with pytest.raises(ValueError, match="Missing required parameters"):
            await autobot.execute_command("required_params", "param1=value1")

    @pytest.mark.asyncio
    async def test_optional_params_command(self, autobot):
        """Test executing command with optional parameters"""
        # Test with no parameters
        result = await autobot.execute_command("optional_params", "")
        assert result == "Optional params result"

        # Test with some optional parameters
        result = await autobot.execute_command("optional_params", "opt1=value1")
        assert result == "Optional params result"

    @pytest.mark.asyncio
    async def test_quoted_parameters(self, autobot):
        """Test handling of quoted parameters"""
        # Test with single quotes
        result = await autobot.execute_command("required_params", "param1='value 1' param2='value 2'")
        assert result == "Required params result"

        # Test with double quotes
        result = await autobot.execute_command("required_params", 'param1="value 1" param2="value 2"')
        assert result == "Required params result"
