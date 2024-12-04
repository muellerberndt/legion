import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.jobs.agent import AgentJob
from src.jobs.base import JobStatus, JobResult
from src.actions.registry import ActionResult
from src.actions.base import ActionSpec, ActionArgument

@pytest.fixture
def mock_openai():
    with patch('src.jobs.agent.AsyncOpenAI') as mock:
        client = AsyncMock()
        mock.return_value = client
        yield client

@pytest.fixture
def mock_action_registry():
    with patch('src.jobs.agent.ActionRegistry') as mock:
        registry = Mock()
        registry.actions = {
            'list': (
                Mock(),
                ActionSpec(
                    name="list",
                    description="List something",
                    arguments=[]
                )
            ),
            'sync': (
                Mock(),
                ActionSpec(
                    name="sync",
                    description="Sync something",
                    arguments=[]
                )
            )
        }
        mock.return_value = registry
        yield registry

@pytest.fixture
def agent_job(mock_openai, mock_action_registry):
    return AgentJob(prompt="List all projects and analyze them")

# ... rest of the tests ... 