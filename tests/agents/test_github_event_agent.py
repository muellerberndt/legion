import pytest
from unittest.mock import AsyncMock
from src.agents.github_event_agent import GithubEventAgent


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

    # Mock the chat completion method
    event_agent.chat_completion = AsyncMock(return_value="This PR adds a new admin function. Security Impact: Yes")

    # Execute
    result = await event_agent.analyze_pr(repo_url, pr_data)

    # Verify
    assert result["has_security_impact"] is True
    assert "This PR adds a new admin function" in result["analysis"]
    assert "Security Impact: Yes" not in result["analysis"]


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

    # Mock the chat completion method
    event_agent.chat_completion = AsyncMock(return_value="This commit modifies error handling. Security Impact: No")

    # Execute
    result = await event_agent.analyze_commit(repo_url, commit_data)

    # Verify
    assert result["has_security_impact"] is False
    assert "This commit modifies error handling" in result["analysis"]
    assert "Security Impact: No" not in result["analysis"]


@pytest.mark.asyncio
async def test_process_analysis_error(event_agent):
    """Test error handling in process_analysis"""
    # Test with malformed response
    result = event_agent._process_analysis("Invalid response without security impact line")

    assert result["has_security_impact"] is False
    assert "Error processing analysis" in result["analysis"]
