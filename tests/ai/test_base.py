"""Tests for the BaseAgent class"""

import pytest
from unittest.mock import patch, AsyncMock, create_autospec, MagicMock
from src.ai.base import BaseAgent
from src.actions.registry import ActionRegistry
from src.actions.base import ActionSpec, ActionArgument, BaseAction
import json


@pytest.fixture
def mock_action_registry():
    """Fixture for mocked ActionRegistry with various test commands"""
    registry = create_autospec(ActionRegistry, instance=True)

    # Mock commands with different parameter configurations
    commands = {
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
    }

    # Create mock handlers
    handlers = {}
    for name, spec in commands.items():
        # Create a mock handler function
        handler = AsyncMock(return_value=f"{name} result" if "db_query" not in name else {"results": [{"id": 1}]})
        handlers[name] = (handler, spec)

    # Special handling for db_query invalid case
    db_query_handler = handlers["db_query"][0]
    original_handler = db_query_handler

    async def execute_with_validation(*args, **kwargs):
        if "invalid_json" in str(args) + str(kwargs):
            return "❌ Invalid query format. Query must be a valid JSON string."
        return await original_handler(*args, **kwargs)

    handlers["db_query"] = (execute_with_validation, commands["db_query"])

    registry._get_agent_command_instructions.return_value = commands
    registry.get_action.side_effect = lambda name: handlers.get(name)
    return registry


@pytest.fixture
def agent(mock_action_registry):
    """Fixture for BaseAgent instance"""
    return BaseAgent(action_registry=mock_action_registry)


class TestBaseAgent:
    """Test BaseAgent functionality"""

    def test_initialization(self, agent, mock_action_registry):
        """Test agent initialization"""
        assert agent.action_registry == mock_action_registry
        assert len(agent.commands) == 5
        assert "no_params" in agent.commands
        assert "required_params" in agent.commands

    @pytest.mark.asyncio
    async def test_execute_command_no_params(self, agent):
        """Test executing command with no parameters"""
        result = await agent.execute_command("no_params", "")
        assert result == "no_params result"

    @pytest.mark.asyncio
    async def test_execute_command_required_params(self, agent):
        """Test executing command with required parameters"""
        # Test with keyword arguments
        result = await agent.execute_command("required_params", "param1=value1 param2=value2")
        assert result == "required_params result"

        # Test with positional arguments
        result = await agent.execute_command("required_params", "value1 value2")
        assert result == "required_params result"

    @pytest.mark.asyncio
    async def test_execute_command_optional_params(self, agent):
        """Test executing command with optional parameters"""
        # Test with no parameters
        result = await agent.execute_command("optional_params", "")
        assert result == "optional_params result"

        # Test with some optional parameters
        result = await agent.execute_command("optional_params", "opt1=value1")
        assert result == "optional_params result"

    @pytest.mark.asyncio
    async def test_execute_command_db_query(self, agent):
        """Test executing db_query command"""
        # Test with valid JSON query
        query = json.dumps({"from": "test", "where": [{"field": "id", "op": "=", "value": 1}]})
        result = await agent.execute_command("db_query", f"query={query}")
        assert isinstance(result, dict)
        assert "results" in result

        # Test with invalid JSON
        result = await agent.execute_command("db_query", "query=invalid_json")
        assert "Invalid query format" in result

    @pytest.mark.asyncio
    async def test_execute_command_quoted_params(self, agent):
        """Test handling of quoted parameters"""
        # Test with single quotes
        result = await agent.execute_command("required_params", "param1='value 1' param2='value 2'")
        assert result == "required_params result"

        # Test with double quotes
        result = await agent.execute_command("required_params", 'param1="value 1" param2="value 2"')
        assert result == "required_params result"

    @pytest.mark.asyncio
    async def test_execute_command_unknown(self, agent):
        """Test executing unknown command"""
        with pytest.raises(ValueError, match="Unknown command: unknown_command"):
            await agent.execute_command("unknown_command", "")

    def test_truncate_result_short(self, agent):
        """Test result truncation with short result"""
        result = "Short result"
        truncated = agent._truncate_result(result)
        assert truncated == result

    def test_truncate_result_long(self, agent):
        """Test result truncation with long result"""
        result = "x" * 5000
        truncated = agent._truncate_result(result)
        assert len(truncated) <= 4000
        assert truncated.endswith("... (truncated)")

    def test_truncate_result_json_dict(self, agent):
        """Test result truncation with JSON dictionary"""
        result = {"results": [{"id": i} for i in range(20)], "other_data": "test"}
        truncated = agent._truncate_result(json.dumps(result))
        data = json.loads(truncated)
        assert len(data["results"]) == 10
        assert "note" in data
        assert "20" in data["note"]
        assert data["other_data"] == "test"

    def test_truncate_result_json_list(self, agent):
        """Test result truncation with JSON list"""
        result = [{"id": i} for i in range(20)]
        truncated = agent._truncate_result(json.dumps(result))
        data = json.loads(truncated)
        assert len(data["results"]) == 10
        assert "note" in data
        assert "20" in data["note"]

    @pytest.mark.asyncio
    async def test_job_handling(self, agent):
        """Test handling of job results"""
        # Mock job manager
        job_manager = MagicMock()
        job_manager.get_job_result = AsyncMock(return_value={"success": True, "data": "Job result"})

        # Add job command to registry
        job_command = ActionSpec(
            name="job_command",
            description="Command that returns a job",
            help_text="Test help",
            agent_hint="Test hint",
            arguments=[
                ActionArgument(name="param1", description="First parameter", required=True),
            ],
        )
        agent.commands["job_command"] = job_command

        # Mock handler that returns a job ID
        handler = AsyncMock(return_value="Job started with ID: job_123")
        agent.action_registry.get_action.side_effect = lambda name: (handler, job_command) if name == "job_command" else None

        with patch("src.jobs.manager.JobManager.get_instance", return_value=job_manager):
            # Test successful job
            result = await agent.execute_command("job_command", "param1=test")
            assert result == {"success": True, "data": "Job result"}

            # Test failed job
            job_manager.get_job_result = AsyncMock(return_value={"success": False, "error": "Job failed"})
            with pytest.raises(ValueError, match="Job failed"):
                await agent.execute_command("job_command", "param1=test")
