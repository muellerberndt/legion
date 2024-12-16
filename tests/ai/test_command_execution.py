import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from src.ai.chatbot import Chatbot
from src.ai.autobot import Autobot
from src.actions.registry import ActionRegistry
from src.models.agent import AgentCommand
import json


@pytest.fixture
def mock_action_registry():
    """Fixture for mocked ActionRegistry with various test commands"""
    registry = MagicMock(spec=ActionRegistry)

    # Mock commands with different parameter configurations
    commands = {
        "no_params": AgentCommand(
            name="no_params",
            description="Command with no parameters",
            help_text="Test help",
            agent_hint="Test hint",
            required_params=[],
            optional_params=[],
            positional_params=[],
        ),
        "required_params": AgentCommand(
            name="required_params",
            description="Command with required parameters",
            help_text="Test help",
            agent_hint="Test hint",
            required_params=["param1", "param2"],
            optional_params=[],
            positional_params=["param1", "param2"],
        ),
        "optional_params": AgentCommand(
            name="optional_params",
            description="Command with optional parameters",
            help_text="Test help",
            agent_hint="Test hint",
            required_params=[],
            optional_params=["opt1", "opt2"],
            positional_params=[],
        ),
        "mixed_params": AgentCommand(
            name="mixed_params",
            description="Command with mixed parameters",
            help_text="Test help",
            agent_hint="Test hint",
            required_params=["required"],
            optional_params=["optional"],
            positional_params=["required"],
        ),
        "db_query": AgentCommand(
            name="db_query",
            description="Database query",
            help_text="Query the database",
            agent_hint="Use for database queries",
            required_params=["query"],
            optional_params=[],
            positional_params=["query"],
        ),
        "job_command": AgentCommand(
            name="job_command",
            description="Command that returns a job",
            help_text="Test help",
            agent_hint="Test hint",
            required_params=["param1"],
            optional_params=[],
            positional_params=["param1"],
        ),
    }

    registry._get_agent_command_instructions.return_value = commands

    # Mock action handlers
    handlers = {
        "no_params": (AsyncMock(return_value="No params result"), None),
        "required_params": (AsyncMock(return_value="Required params result"), None),
        "optional_params": (AsyncMock(return_value="Optional params result"), None),
        "mixed_params": (AsyncMock(return_value="Mixed params result"), None),
        "db_query": (AsyncMock(return_value={"results": [{"id": 1}]}), None),
        "job_command": (AsyncMock(return_value="Job started with ID: job_123"), None),
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

        # Test with missing parameters - this should work since validation is not implemented
        result = await chatbot.execute_command("required_params", "param1=value1")
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

        # Test with both required and optional parameters
        result = await chatbot.execute_command("mixed_params", "required=value1 optional=value2")
        assert result == "Mixed params result"

    @pytest.mark.asyncio
    async def test_db_query_command(self, chatbot):
        """Test executing db_query command"""
        # Test with valid JSON query
        query = json.dumps({"collection": "test", "filter": {}, "limit": 10})
        result = await chatbot.execute_command("db_query", f"query={query}")
        assert isinstance(result, dict)
        assert "results" in result

        # Test with invalid JSON
        with pytest.raises(ValueError, match="Invalid query format"):
            await chatbot.execute_command("db_query", "query=invalid_json")

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
        result = await autobot._execute_command_with_params(
            "required_params",
            autobot.action_registry.get_action("required_params")[0],
            autobot.commands["required_params"],
            "param1=value1 param2=value2",
        )
        assert result == "Required params result"

        # Test with positional arguments
        result = await autobot._execute_command_with_params(
            "required_params",
            autobot.action_registry.get_action("required_params")[0],
            autobot.commands["required_params"],
            "value1 value2",
        )
        assert result == "Required params result"

    @pytest.mark.asyncio
    async def test_optional_params_command(self, autobot):
        """Test executing command with optional parameters"""
        # Test with no parameters
        result = await autobot._execute_command_with_params(
            "optional_params",
            autobot.action_registry.get_action("optional_params")[0],
            autobot.commands["optional_params"],
            "",
        )
        assert result == "Optional params result"

        # Test with some optional parameters
        result = await autobot._execute_command_with_params(
            "optional_params",
            autobot.action_registry.get_action("optional_params")[0],
            autobot.commands["optional_params"],
            "opt1=value1",
        )
        assert result == "Optional params result"

    @pytest.mark.asyncio
    async def test_db_query_command(self, autobot):
        """Test executing db_query command"""
        # Test with valid JSON query
        query = json.dumps({"collection": "test", "filter": {}, "limit": 10})
        result = await autobot._execute_command_with_params(
            "db_query", autobot.action_registry.get_action("db_query")[0], autobot.commands["db_query"], f"query={query}"
        )
        assert isinstance(result, dict)
        assert "results" in result

        # Test with invalid JSON
        with pytest.raises(ValueError, match="Invalid query format"):
            await autobot._execute_command_with_params(
                "db_query",
                autobot.action_registry.get_action("db_query")[0],
                autobot.commands["db_query"],
                "query=invalid_json",
            )

    @pytest.mark.asyncio
    async def test_quoted_parameters(self, autobot):
        """Test handling of quoted parameters"""
        # Test with single quotes
        result = await autobot._execute_command_with_params(
            "required_params",
            autobot.action_registry.get_action("required_params")[0],
            autobot.commands["required_params"],
            "param1='value 1' param2='value 2'",
        )
        assert result == "Required params result"

        # Test with double quotes
        result = await autobot._execute_command_with_params(
            "required_params",
            autobot.action_registry.get_action("required_params")[0],
            autobot.commands["required_params"],
            'param1="value 1" param2="value 2"',
        )
        assert result == "Required params result"
