import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from src.actions.job import ListJobsAction, GetJobResultAction
from src.jobs.manager import JobManager
from src.jobs.base import JobStatus, Job, JobResult
from src.models.job import JobRecord


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


@pytest.mark.asyncio
async def test_get_job_result_action():
    """Test getting job results"""
    action = GetJobResultAction()

    # Test getting most recent job when none exists
    with patch("src.jobs.manager.JobManager.get_most_recent_finished_job") as mock_get_recent:
        mock_get_recent.return_value = None
        result = await action.execute()
        assert "No completed jobs found" in str(result)

    # Test getting running job from memory
    mock_job = Mock(spec=Job)
    mock_job.id = "test-job-1"
    mock_job.type = "test"
    mock_job.status = JobStatus.RUNNING.value.upper()
    mock_job.started_at = datetime.utcnow()
    mock_job.completed_at = None
    mock_job.result = JobResult(success=None, message="Running test job")
    mock_job.result.outputs = ["Output 1"]
    mock_job.result.data = {"key": "value"}

    with (
        patch("src.jobs.manager.JobManager.get_job") as mock_get_job,
        patch("src.jobs.manager.JobManager.get_most_recent_finished_job") as mock_get_recent,
    ):
        mock_get_job.return_value = mock_job
        mock_get_recent.return_value = None
        result = await action.execute("test-job-1")
        result_str = str(result)
        assert "test-job-1" in result_str
        assert any(status in result_str for status in ["RUNNING", "running"])
        assert "Running test job" in result_str

    # Test getting completed job from database
    mock_record = Mock(spec=JobRecord)
    mock_record.id = "test-job-2"
    mock_record.type = "test"
    mock_record.status = JobStatus.COMPLETED.value.upper()
    mock_record.started_at = datetime.utcnow()
    mock_record.completed_at = datetime.utcnow()
    mock_record.success = True
    mock_record.message = "Completed test job"
    mock_record.outputs = ["Output 1", "Output 2"]
    mock_record.data = {"key": "value"}

    # Configure mock session
    mock_session_instance = Mock()
    mock_session_instance.query.return_value.filter_by.return_value.first.return_value = mock_record

    with (
        patch("src.jobs.manager.JobManager.get_job") as mock_get_job,
        patch("src.jobs.manager.JobManager.get_most_recent_finished_job") as mock_get_recent,
        patch("src.jobs.manager.JobManager.get_session") as mock_get_session,
    ):
        mock_get_job.return_value = None  # Not in memory
        mock_get_recent.return_value = None
        mock_get_session.return_value.__enter__.return_value = mock_session_instance
        result = await action.execute("test-job-2")
        result_str = str(result)
        assert "test-job-2" in result_str
        assert any(status in result_str.upper() for status in ["COMPLETED", "RUNNING"])
        assert "Completed test job" in result_str

    # Test job not found
    with (
        patch("src.jobs.manager.JobManager.get_job") as mock_get_job,
        patch("src.jobs.manager.JobManager.get_most_recent_finished_job") as mock_get_recent,
        patch("src.jobs.manager.JobManager.get_session") as mock_get_session,
    ):
        # Configure mock session to return None for job not found
        mock_session_instance = Mock()
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = None
        mock_query.filter_by.return_value = mock_filter
        mock_session_instance.query.return_value = mock_query
        mock_get_session.return_value.__enter__.return_value = mock_session_instance

        mock_get_job.return_value = None  # Not in memory
        mock_get_recent.return_value = None
        result = await action.execute("non-existent-job")
        assert "Job non-existent-job not found" in str(result)

    # Test error handling
    with patch("src.jobs.manager.JobManager.get_job") as mock_get_job:
        mock_get_job.side_effect = Exception("Test error")
        result = await action.execute("test-job")
        assert "Failed to get job result" in str(result)
