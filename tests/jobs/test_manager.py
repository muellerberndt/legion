import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.jobs.manager import JobManager
from src.jobs.base import Job, JobType, JobStatus, JobResult
from datetime import datetime
import asyncio
from src.models.job import JobRecord


@pytest.fixture
async def job_manager():
    """Create and start a job manager for testing"""
    manager = JobManager()
    manager._jobs.clear()  # Ensure clean state
    await manager.start()  # Start the manager
    yield manager
    await manager.stop()  # Clean up after tests


@pytest.fixture
def mock_job():
    job = Mock(spec=Job)
    # Basic attributes
    job.id = "test-job"
    job.type = JobType.INDEXER
    job.status = JobStatus.PENDING
    job.error = None

    # Timestamps
    job.started_at = None
    job.completed_at = None

    # Result
    mock_result = Mock(spec=JobResult)
    mock_result.success = True
    mock_result.message = "Test result"
    mock_result.outputs = []
    mock_result.data = {}
    mock_result.get_output.return_value = "Test result"
    job.result = mock_result

    # Mock methods
    job.start = AsyncMock()
    job.stop = AsyncMock()

    # Add to_dict method
    job.to_dict.return_value = {
        "id": job.id,
        "type": job.type.value,
        "status": job.status.value,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "result": mock_result.get_output(),
        "error": job.error,
    }

    return job


@pytest.fixture
def mock_session():
    with patch("src.backend.database.DBSessionMixin.get_session") as mock:
        session = Mock()
        session.__enter__ = Mock(return_value=session)
        session.__exit__ = Mock(return_value=None)
        mock.return_value = session
        yield session


@pytest.fixture
def mock_notifier():
    with patch("src.jobs.notification.JobNotifier") as mock:
        notifier = Mock()
        notifier.notify_completion = AsyncMock()
        mock.return_value = notifier
        yield notifier


@pytest.mark.asyncio
async def test_submit_job_basic(job_manager, mock_job, mock_session, mock_notifier):
    """Test basic job submission"""
    job_id = await job_manager.submit_job(mock_job)
    assert job_id == mock_job.id
    assert mock_job.id in job_manager._jobs
    assert mock_job.id in job_manager._tasks

    # Verify database record was created
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_job_lifecycle_success(job_manager, mock_job, mock_session, mock_notifier):
    """Test complete job lifecycle with successful completion"""
    # Submit job
    job_id = await job_manager.submit_job(mock_job)

    # Verify initial state
    assert mock_job.status == JobStatus.PENDING

    # Simulate job starting
    mock_job.status = JobStatus.RUNNING
    mock_job.started_at = datetime.utcnow()

    # Simulate successful completion
    mock_job.status = JobStatus.COMPLETED
    mock_job.completed_at = datetime.utcnow()
    mock_job.result.message = "Job completed successfully"

    # Wait for job to complete
    task = job_manager._tasks[job_id]
    await task

    # Verify final state
    assert mock_job.status == JobStatus.COMPLETED
    assert mock_job.result.success is True

    # Verify notification was sent
    mock_notifier.notify_completion.assert_called()
    call_args = mock_notifier.notify_completion.call_args[1]
    assert call_args["status"] == JobStatus.COMPLETED.value
    assert call_args["message"] == "Job completed successfully"


@pytest.mark.asyncio
async def test_job_lifecycle_failure(job_manager, mock_job, mock_session, mock_notifier):
    """Test job lifecycle with failure"""
    job_id = await job_manager.submit_job(mock_job)

    # Simulate job failure
    error_msg = "Test error occurred"
    mock_job.start.side_effect = Exception(error_msg)

    # Wait for job to complete
    task = job_manager._tasks[job_id]
    await task

    # Verify error state
    assert mock_job.status == JobStatus.FAILED
    assert mock_job.error == error_msg

    # Verify failure notification
    mock_notifier.notify_completion.assert_called()
    call_args = mock_notifier.notify_completion.call_args[1]
    assert call_args["status"] == JobStatus.FAILED.value
    assert call_args["message"] == error_msg


@pytest.mark.asyncio
async def test_job_cancellation(job_manager, mock_job, mock_session, mock_notifier):
    """Test job cancellation"""
    job_id = await job_manager.submit_job(mock_job)

    # Cancel the job
    success = await job_manager.stop_job(job_id)
    assert success

    # Verify cancellation state
    assert mock_job.status == JobStatus.CANCELLED
    assert job_id not in job_manager._jobs
    assert job_id not in job_manager._tasks

    # Verify cancellation notification
    mock_notifier.notify_completion.assert_called()
    call_args = mock_notifier.notify_completion.call_args[1]
    assert call_args["status"] == JobStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_concurrent_jobs(job_manager, mock_session, mock_notifier):
    """Test handling multiple concurrent jobs"""
    # Create multiple jobs
    jobs = []
    for i in range(3):
        job = AsyncMock(spec=Job)
        job.id = f"test-job-{i}"
        job.type = JobType.INDEXER
        job.status = JobStatus.PENDING
        job.error = None
        job.started_at = None
        job.completed_at = None

        # Set up the start method to simulate successful completion
        async def mock_start(job_num=i):
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            return None

        job.start.side_effect = mock_start

        result = Mock(spec=JobResult)
        result.success = True
        result.message = f"Job {i} completed"
        result.outputs = []
        result.data = {}
        result.get_output = Mock(return_value=f"Job {i} completed")
        job.result = result

        # Add to_dict method
        job.to_dict.return_value = {
            "id": job.id,
            "type": job.type.value,
            "status": job.status.value,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "result": result.get_output(),
            "error": job.error,
        }

        jobs.append(job)

    # Submit all jobs
    tasks = []
    for job in jobs:
        job_id = await job_manager.submit_job(job)
        tasks.append(job_manager._tasks[job_id])

    # Wait for all jobs to complete
    await asyncio.gather(*tasks)

    # Verify all jobs completed
    assert len(mock_notifier.notify_completion.mock_calls) == len(jobs)
    for job in jobs:
        assert job.status == JobStatus.COMPLETED


@pytest.mark.asyncio
async def test_job_cleanup(job_manager, mock_job, mock_session, mock_notifier):
    """Test proper cleanup of job resources"""
    job_id = await job_manager.submit_job(mock_job)

    # Simulate job completion
    task = job_manager._tasks[job_id]
    await task

    # Verify cleanup
    assert job_id not in job_manager._tasks
    assert mock_session.commit.called

    # Force cleanup
    await job_manager.stop()
    assert len(job_manager._jobs) == 0
    assert len(job_manager._tasks) == 0


@pytest.mark.asyncio
async def test_job_result_handling(job_manager, mock_job, mock_session, mock_notifier):
    """Test proper handling of job results"""
    # Set up test outputs
    outputs = ["Output 1", "Output 2"]
    data = {"key": "value"}
    mock_job.result.outputs = outputs
    mock_job.result.data = data

    # Mock the JobRecord creation
    def mock_add(record):
        record.outputs = outputs
        record.data = data
        return record

    mock_session.add.side_effect = mock_add

    job_id = await job_manager.submit_job(mock_job)

    # Wait for job to complete
    task = job_manager._tasks[job_id]
    await task

    # Verify result was saved to database
    mock_session.commit.assert_called()
    job_record = mock_session.add.call_args[0][0]
    assert isinstance(job_record, JobRecord)
    assert job_record.outputs == outputs
    assert job_record.data == data


@pytest.mark.asyncio
async def test_notification_formatting(job_manager, mock_job, mock_session, mock_notifier):
    """Test job notification formatting"""
    job_id = await job_manager.submit_job(mock_job)

    # Wait for job to complete
    task = job_manager._tasks[job_id]
    await task

    # Verify notification format
    mock_notifier.notify_completion.assert_called()
    call_args = mock_notifier.notify_completion.call_args[1]

    # Should include job ID
    assert call_args["job_id"] == job_id
    assert call_args["job_type"] == mock_job.type.value
    assert call_args["status"] == JobStatus.COMPLETED.value
    assert call_args["message"] == mock_job.result.message


@pytest.mark.asyncio
async def test_list_jobs(job_manager, mock_job, mock_session):
    """Test listing jobs"""
    # Add some test jobs
    job1 = mock_job

    job2 = Mock(spec=Job)
    job2.id = "test-job-2"
    job2.type = JobType.INDEXER
    job2.status = JobStatus.RUNNING
    job2.error = None
    job2.started_at = None
    job2.completed_at = None

    # Set up result for job2
    mock_result2 = Mock(spec=JobResult)
    mock_result2.success = True
    mock_result2.message = "Test result 2"
    mock_result2.outputs = []
    mock_result2.data = {}
    mock_result2.get_output.return_value = "Test result 2"
    job2.result = mock_result2

    # Mock methods
    job2.start = AsyncMock()
    job2.stop = AsyncMock()

    # Set up to_dict for job2
    job2.to_dict.return_value = {
        "id": job2.id,
        "type": job2.type.value,
        "status": job2.status.value,
        "started_at": job2.started_at,
        "completed_at": job2.completed_at,
        "result": mock_result2.get_output() if mock_result2 else None,
        "error": job2.error,
    }

    # Submit jobs
    await job_manager.submit_job(job1)
    await job_manager.submit_job(job2)

    # Get job list
    jobs = job_manager.list_jobs()

    # Verify results
    assert len(jobs) == 2
    assert any(j["id"] == job1.id for j in jobs)
    assert any(j["id"] == job2.id for j in jobs)
