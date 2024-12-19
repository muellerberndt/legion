import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from src.actions.job import ListJobsAction
from src.jobs.manager import JobManager


@pytest.mark.asyncio
async def test_list_jobs_action():
    """Test listing jobs"""
    action = ListJobsAction()

    # Test empty list
    with patch("src.jobs.manager.JobManager.list_jobs") as mock_list:
        mock_list.return_value = []
        result = await action.execute()
        assert "No jobs found" in str(result)

    # Test with jobs
    with patch("src.jobs.manager.JobManager.list_jobs") as mock_list:
        mock_list.return_value = [
            {
                "id": "test-1",
                "type": "test",
                "status": "RUNNING",
                "started_at": "2024-01-01T00:00:00",
                "completed_at": None,
                "success": None,
                "message": "Test job",
                "outputs": ["Output 1"],
                "data": None,
            }
        ]

        result = await action.execute()
        result_str = str(result)
        assert "test-1" in result_str
        assert "RUNNING" in result_str
        assert "Test job" in result_str

    # Test with status filter
    with patch("src.jobs.manager.JobManager.list_jobs") as mock_list:
        mock_list.return_value = [
            {
                "id": "test-2",
                "type": "test",
                "status": "COMPLETED",
                "started_at": "2024-01-01T00:00:00",
                "completed_at": "2024-01-01T00:01:00",
                "success": True,
                "message": "Completed job",
                "outputs": ["Output 1"],
                "data": None,
            }
        ]

        result = await action.execute("completed")
        result_str = str(result)
        assert "test-2" in result_str
        assert "COMPLETED ✓" in result_str
        assert "Completed job" in result_str

    # Test invalid status
    result = await action.execute("invalid_status")
    assert "Invalid status filter" in str(result)

    # Test error handling
    with patch("src.jobs.manager.JobManager.list_jobs") as mock_list:
        mock_list.side_effect = Exception("Test error")
        result = await action.execute()
        assert "Failed to list jobs" in str(result)
