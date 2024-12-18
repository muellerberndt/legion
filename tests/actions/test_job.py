import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from src.actions.job import ListJobsAction
from src.jobs.manager import JobManager


@pytest.mark.asyncio
async def test_list_jobs_action():
    """Test listing jobs in list format"""
    # Create a mock instance
    manager_instance = Mock()
    manager_instance.list_jobs = Mock()

    # Create the action instance
    action = ListJobsAction()
    action.logger = Mock()

    # Test with no jobs
    with patch.object(JobManager, "_instance", manager_instance):
        manager_instance.list_jobs.return_value = []
        result = await action.execute()
        assert "No jobs found." in str(result)

        # Test with running jobs
        now = datetime.utcnow()
        jobs = [
            {"id": "job1", "type": "indexer", "status": "running", "started_at": now.isoformat(), "completed_at": None},
            {
                "id": "job2",
                "type": "sync",
                "status": "completed",
                "started_at": now.isoformat(),
                "completed_at": now.isoformat(),
            },
        ]
        manager_instance.list_jobs.return_value = jobs

        result = await action.execute()
        result_str = str(result)
        # Check list format
        assert "🔹 Job job1" in result_str
        assert "Type: indexer" in result_str
        assert "Status: running" in result_str
        assert now.isoformat() in result_str
        assert "🔹 Job job2" in result_str
        assert "Type: sync" in result_str
        assert "Status: completed" in result_str
        assert "Completed:" in result_str  # Only completed jobs show completion time

        # Test error handling
        manager_instance.list_jobs.side_effect = Exception("Test error")
        result = await action.execute()
        assert "Failed to list jobs: Test error" in str(result)
