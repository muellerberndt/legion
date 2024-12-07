import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.agents.base_agent import BaseAgent
from src.actions.base import ActionSpec, ActionArgument
import asyncio


@pytest.fixture(autouse=True)
async def cleanup_async():
    """Cleanup any async resources after each test"""
    yield
    # Get all tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    # Cancel them
    [task.cancel() for task in tasks]
    # Wait until all tasks are cancelled
    await asyncio.gather(*tasks, return_exceptions=True)


@pytest.fixture
async def mock_openai():
    with patch("src.agents.base_agent.AsyncOpenAI") as mock:
        client = AsyncMock()
        response = Mock()
        message = Mock()
        message.content = "Test response"
        choice = Mock()
        choice.message = message
        response.choices = [choice]
        client.chat.completions.create = AsyncMock(return_value=response)
        client.close = AsyncMock()
        mock.return_value = client
        yield client
        await client.close()


@pytest.fixture
async def mock_action_registry():
    with patch("src.agents.base_agent.ActionRegistry") as mock:
        registry = Mock()

        # Create an async handler that returns a string
        async def async_execute(*args, **kwargs):
            return "Test command executed"

        handler = AsyncMock()
        handler.execute = AsyncMock(side_effect=async_execute)

        actions = {
            "test": (
                handler,
                ActionSpec(
                    name="test",
                    description="Test command",
                    help_text="Test help text",
                    agent_hint="Use this command for testing",
                    arguments=[ActionArgument(name="options", description="Test options", required=False)],
                ),
            )
        }
        registry.get_actions.return_value = actions
        registry.get_action.side_effect = lambda name: actions.get(name)
        mock.return_value = registry
        yield registry


@pytest.fixture
async def base_agent(mock_openai, mock_action_registry):
    agent = BaseAgent(custom_prompt="You are a test agent")
    yield agent
    if hasattr(agent.client, "close"):
        await agent.client.close()


@pytest.mark.asyncio
async def test_base_agent_init():
    """Test base agent initialization"""
    agent = BaseAgent(custom_prompt="Test prompt")
    assert "Test prompt" in agent.system_prompt
    assert isinstance(agent.commands, dict)


@pytest.mark.asyncio
async def test_base_agent_chat_completion(base_agent, mock_openai):
    """Test chat completion"""
    messages = [{"role": "user", "content": "Test message"}]
    response = await base_agent.chat_completion(messages)
    assert response == "Test response"
    assert mock_openai.chat.completions.create.called


@pytest.mark.asyncio
async def test_base_agent_error_handling(base_agent, mock_openai):
    """Test error handling in chat completion"""
    mock_openai.chat.completions.create.side_effect = Exception("Test error")

    with pytest.raises(Exception):
        await base_agent.chat_completion([{"role": "user", "content": "Test"}])
