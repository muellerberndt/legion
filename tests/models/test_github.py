import pytest
from datetime import datetime, timezone
from src.models.github import GitHubRepoState
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, Mock, patch

@pytest.fixture
async def mock_db_session():
    """Create a mock async database session"""
    session = AsyncMock(spec=AsyncSession)
    
    # Mock get method to return different results based on state
    mock_state = {}
    
    async def mock_get(model_class, key):
        return mock_state.get(key)
        
    async def mock_refresh(instance):
        pass
        
    session.get = AsyncMock(side_effect=mock_get)
    session.refresh = AsyncMock(side_effect=mock_refresh)
    session.add = AsyncMock()
    session.delete = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    
    # Store state for test verification
    session._mock_state = mock_state
    
    return session

def test_github_repo_state_creation():
    """Test creating a GitHubRepoState instance with basic attributes"""
    now = datetime.now(timezone.utc)
    repo_state = GitHubRepoState(
        repo_url="https://github.com/owner/repo",
        last_commit_sha="abc123",
        last_pr_number=42,
        created_at=now,
        updated_at=now
    )
    
    assert repo_state.repo_url == "https://github.com/owner/repo"
    assert repo_state.last_commit_sha == "abc123"
    assert repo_state.last_pr_number == 42
    assert repo_state.last_check is None
    assert isinstance(repo_state.created_at, datetime)
    assert isinstance(repo_state.updated_at, datetime)

def test_github_repo_state_to_dict():
    """Test the to_dict method handles all fields correctly"""
    now = datetime.now(timezone.utc)
    repo_state = GitHubRepoState(
        repo_url="https://github.com/owner/repo",
        last_commit_sha="abc123",
        last_pr_number=42,
        last_check=now,
        created_at=now,
        updated_at=now
    )
    
    result = repo_state.to_dict()
    
    assert result["repo_url"] == "https://github.com/owner/repo"
    assert result["last_commit_sha"] == "abc123"
    assert result["last_pr_number"] == 42
    assert result["last_check"] == now.isoformat()
    assert result["created_at"] == now.isoformat()
    assert result["updated_at"] == now.isoformat()

def test_github_repo_state_to_dict_with_none_dates():
    """Test the to_dict method handles None dates correctly"""
    now = datetime.now(timezone.utc)
    repo_state = GitHubRepoState(
        repo_url="https://github.com/owner/repo",
        last_commit_sha="abc123",
        last_pr_number=42,
        last_check=None,
        created_at=now,
        updated_at=now
    )
    
    result = repo_state.to_dict()
    
    assert result["last_check"] is None
    assert result["created_at"] is not None
    assert result["updated_at"] is not None

@pytest.mark.asyncio
async def test_github_repo_state_db_operations(mock_db_session: AsyncSession):
    """Test database operations with GitHubRepoState"""
    repo_url = "https://github.com/owner/repo"
    
    # Create new repo state
    repo_state = GitHubRepoState(
        repo_url=repo_url,
        last_commit_sha="abc123",
        last_pr_number=42
    )
    
    # Add to database
    mock_db_session.add(repo_state)
    await mock_db_session.commit()
    
    # Store in mock state for get operations
    mock_db_session._mock_state[repo_url] = repo_state
    
    # Query and verify
    result = await mock_db_session.get(GitHubRepoState, repo_url)
    assert result is not None
    assert result.repo_url == repo_url
    assert result.last_commit_sha == "abc123"
    assert result.last_pr_number == 42
    
    # Update
    result.last_commit_sha = "def456"
    await mock_db_session.commit()
    
    # Query again and verify update
    updated = await mock_db_session.get(GitHubRepoState, repo_url)
    assert updated.last_commit_sha == "def456"
    
    # Delete
    await mock_db_session.delete(result)
    await mock_db_session.commit()
    
    # Remove from mock state
    mock_db_session._mock_state.pop(repo_url, None)
    
    # Verify deletion
    deleted = await mock_db_session.get(GitHubRepoState, repo_url)
    assert deleted is None
    
    # Cleanup
    await mock_db_session.rollback() 