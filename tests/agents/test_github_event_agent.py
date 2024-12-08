import pytest
from unittest.mock import AsyncMock
from src.agents.github_event_agent import GithubEventAgent, AgentResult


@pytest.fixture
def event_agent():
    """Create event agent with mocked dependencies"""
    agent = GithubEventAgent()
    return agent


@pytest.mark.asyncio
async def test_agent_analyze_pr(event_agent):
    """Test analyzing a pull request"""
    # Setup
    repo_url = "https://github.com/test/repo"
    pr_data = {
        "number": 1,
        "title": "Test PR",
        "body": "Test description",
        "html_url": "https://github.com/test/repo/pull/1",
        "changed_files": 2,
        "additions": 10,
        "deletions": 5,
    }

    # Mock the execute_task method
    event_agent.execute_task = AsyncMock(
        return_value=AgentResult(success=True, data={"result": {"analysis": "Test analysis"}})
    )

    # Execute
    result = await event_agent.analyze_pr(repo_url, pr_data)

    # Verify
    assert "Test analysis" in result
    event_agent.execute_task.assert_called_once()
    call_args = event_agent.execute_task.call_args[0][0]
    assert call_args["event_type"] == "pr"
    assert call_args["event_data"]["repository"] == repo_url


@pytest.mark.asyncio
async def test_agent_analyze_commit(event_agent):
    """Test analyzing a commit"""
    # Setup
    repo_url = "https://github.com/test/repo"
    commit_data = {
        "sha": "123abc",
        "commit": {"message": "Test commit", "author": {"name": "test-user"}},
        "html_url": "https://github.com/test/repo/commit/123",
    }

    # Mock the execute_task method
    event_agent.execute_task = AsyncMock(
        return_value=AgentResult(success=True, data={"result": {"analysis": "Test analysis"}})
    )

    # Execute
    result = await event_agent.analyze_commit(repo_url, commit_data)

    # Verify
    assert "Test analysis" in result
    event_agent.execute_task.assert_called_once()
    call_args = event_agent.execute_task.call_args[0][0]
    assert call_args["event_type"] == "commit"
    assert call_args["event_data"]["repository"] == repo_url


@pytest.mark.asyncio
async def test_agent_execute_step(event_agent):
    """Test executing a step"""
    # Setup
    event_agent.state = {
        "event_type": "pr",
        "event_data": {"repository": "test/repo", "message": "Test message", "changes": {"test": "data"}},
    }

    # Mock chat_completion
    event_agent.chat_completion = AsyncMock(return_value="Test analysis")

    # Execute
    result = await event_agent.execute_step()

    # Verify
    assert result.success is True
    assert "result" in event_agent.state
    assert event_agent.state["result"]["analysis"] == "Test analysis"


def test_agent_is_task_complete(event_agent):
    """Test task completion check"""
    # Setup - no result
    event_agent.state = {}
    assert event_agent.is_task_complete() is False

    # Setup - with result
    event_agent.state["result"] = {"analysis": "Test"}
    assert event_agent.is_task_complete() is True


@pytest.mark.asyncio
async def test_agent_plan_next_step(event_agent):
    """Test planning next step"""
    # Setup - initial state
    current_state = {"event_type": "pr", "event_data": {"test": "data"}}

    # Execute
    next_step = await event_agent.plan_next_step(current_state)

    # Verify
    assert next_step["action"] == "analyze_pr"

    # Setup - completed state
    current_state["result"] = {"analysis": "Test"}
    next_step = await event_agent.plan_next_step(current_state)

    # Verify
    assert next_step["action"] == "complete"
