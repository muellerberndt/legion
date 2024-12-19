import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.jobs.manager import JobManager
from src.jobs.base import Job, JobStatus, JobResult
from datetime import datetime, timedelta
import asyncio
from src.models.job import JobRecord


@pytest.fixture
async def job_manager():
    """Create and start a job manager for testing"""
    manager = JobManager()
    manager.initialize()  # Explicitly call initialize
    await manager.start()  # Start the manager
    yield manager
    await manager.stop()  # Clean up after tests


@pytest.fixture
def mock_job():
    """Create a mock job for testing"""
    job = Mock(spec=Job)
    # Basic attributes
    job.id = "test-job"
    job.type = "indexer"
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
    async def mock_start():
        job.status = JobStatus.COMPLETED
        job.started_at = datetime.utcnow()
        job.completed_at = datetime.utcnow()
        return True

    job.start = AsyncMock(side_effect=mock_start)
    job.stop = AsyncMock()

    # Add to_dict method
    job.to_dict.return_value = {
        "id": job.id,
        "type": job.type,
        "status": job.status.value,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "result": mock_result.get_output(),
        "error": job.error,
    }

    return job


@pytest.fixture
def mock_session():
    """Create mock database session"""
    with patch("src.backend.database.DBSessionMixin.get_session") as mock:
        session = Mock()
        session.__enter__ = Mock(return_value=session)
        session.__exit__ = Mock(return_value=None)

        # Create a mock record that can be modified
        job_record = Mock(spec=JobRecord)
        job_record.status = None
        job_record.success = None
        job_record.message = None
        job_record.outputs = []
        job_record.data = {}
        job_record.id = "test-job"

        # Set up query chain
        query_mock = Mock()
        query_mock.filter = Mock(return_value=query_mock)
        query_mock.order_by = Mock(return_value=query_mock)
        query_mock.first = Mock(return_value=job_record)
        query_mock.all = Mock(return_value=[job_record])
        session.query = Mock(return_value=query_mock)

        # Set up add and commit
        session.add = Mock()
        session.commit = Mock()
        session.delete = Mock()

        mock.return_value = session
        yield session


@pytest.fixture
def mock_notifier():
    """Create mock notifier"""
    with patch("src.jobs.notification.JobNotifier") as mock:
        notifier = Mock()
        notifier.notify_completion = AsyncMock()
        mock.return_value = notifier
        yield notifier


@pytest.mark.asyncio
async def test_submit_job_basic(job_manager, mock_job, mock_session):
    """Test basic job submission"""
    job_id = await job_manager.submit_job(mock_job)
    assert job_id == mock_job.id
    assert job_id in job_manager._running_jobs
    assert job_id in job_manager._tasks


@pytest.mark.asyncio
async def test_job_lifecycle_success(job_manager, mock_job, mock_session, mock_notifier):
    """Test successful job lifecycle"""
    # Configure mock record
    mock_record = mock_session.query.return_value.filter.return_value.first.return_value

    # Configure mock job to complete successfully
    mock_job.start = AsyncMock()
    mock_job.start.side_effect = lambda: mock_job.complete_job()

    # Add complete_job method to mock
    def complete_job():
        mock_job.status = JobStatus.COMPLETED
        mock_job.started_at = datetime.utcnow()
        mock_job.completed_at = datetime.utcnow()
        mock_job.result = JobResult(success=True, message="Test completed")

    mock_job.complete_job = complete_job

    # Set up job manager with notifier
    job_manager._notifier = mock_notifier

    job_id = await job_manager.submit_job(mock_job)
    task = job_manager._tasks[job_id]
    await task

    # Verify job record was updated only after completion
    assert mock_record.status == "completed"
    assert mock_record.success is True
    assert mock_record.message == "Test completed"
    mock_session.commit.assert_called()

    # Verify notification was sent
    mock_notifier.notify_completion.assert_awaited_once_with(
        job_id=job_id,
        job_type=mock_job.type,
        status=JobStatus.COMPLETED.value,
        message="Test completed",
        outputs=[],
        data={},
        started_at=mock_job.started_at,
        completed_at=mock_job.completed_at,
    )


@pytest.mark.asyncio
async def test_job_lifecycle_failure(job_manager, mock_job, mock_session, mock_notifier):
    """Test job failure handling"""
    error_msg = "Test error occurred"

    # Configure mock record
    mock_record = mock_session.query.return_value.filter.return_value.first.return_value

    # Configure mock job to fail
    mock_job.start = AsyncMock()
    mock_job.start.side_effect = lambda: mock_job.fail_job()

    # Add fail_job method to mock
    def fail_job():
        mock_job.status = JobStatus.FAILED
        mock_job.started_at = datetime.utcnow()
        mock_job.completed_at = datetime.utcnow()
        mock_job.error = error_msg
        raise Exception(error_msg)

    mock_job.fail_job = fail_job

    # Set up job manager with notifier
    job_manager._notifier = mock_notifier

    job_id = await job_manager.submit_job(mock_job)
    task = job_manager._tasks[job_id]
    await task

    # Verify error was stored only after failure
    assert mock_record.status == "failed"
    assert mock_record.success is False
    assert mock_record.message == error_msg
    mock_session.commit.assert_called()

    # Verify notification was sent
    mock_notifier.notify_completion.assert_awaited_once_with(
        job_id=job_id,
        job_type=mock_job.type,
        status=JobStatus.FAILED.value,
        message=error_msg,
        started_at=mock_job.started_at,
        completed_at=mock_job.completed_at,
    )


@pytest.mark.asyncio
async def test_job_cancellation(job_manager, mock_job, mock_session):
    """Test job cancellation"""
    # Configure mock record
    mock_record = Mock(spec=JobRecord)
    mock_session.query.return_value.filter.return_value.first.return_value = mock_record

    job_id = await job_manager.submit_job(mock_job)

    # Cancel the job
    success = await job_manager.stop_job(job_id)
    assert success

    # Verify cancellation state
    assert mock_record.status == JobStatus.CANCELLED.value
    assert job_id not in job_manager._running_jobs
    assert job_id not in job_manager._tasks
    mock_session.commit.assert_called()


@pytest.mark.asyncio
async def test_concurrent_jobs(job_manager, mock_session):
    """Test running multiple jobs concurrently"""
    # Create mock record that will be returned for all queries
    mock_record = Mock(spec=JobRecord)
    mock_record.status = JobStatus.COMPLETED.value
    mock_session.query.return_value.filter.return_value.all.return_value = [mock_record] * 3

    jobs = []
    for i in range(3):
        job = Mock(spec=Job)
        job.id = f"test-job-{i}"
        job.type = "test"
        job.status = JobStatus.PENDING
        job.start = AsyncMock()
        job.result = Mock(success=True, message=f"Job {i} completed", outputs=[])
        jobs.append(job)

    # Submit all jobs
    job_ids = []
    for job in jobs:
        job_id = await job_manager.submit_job(job)
        job_ids.append(job_id)

    # Wait for all jobs
    tasks = [job_manager._tasks[job_id] for job_id in job_ids]
    await asyncio.gather(*tasks)

    # Verify all jobs completed
    completed_jobs = mock_session.query.return_value.filter.return_value.all()
    assert len(completed_jobs) == len(jobs)


@pytest.mark.asyncio
async def test_job_cleanup(job_manager, mock_job, mock_session):
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
    assert len(job_manager._running_jobs) == 0
    assert len(job_manager._tasks) == 0


@pytest.mark.asyncio
async def test_job_result_handling(job_manager, mock_job, mock_session, mock_notifier):
    """Test proper handling of job results"""
    # Set up test outputs
    outputs = ["Output 1", "Output 2"]
    data = {"key": "value"}

    # Configure mock record
    mock_record = mock_session.query.return_value.filter.return_value.first.return_value

    # Configure mock job to complete with outputs
    mock_job.start = AsyncMock()
    mock_job.start.side_effect = lambda: mock_job.complete_with_outputs()

    # Add complete_with_outputs method to mock
    def complete_with_outputs():
        mock_job.status = JobStatus.COMPLETED
        mock_job.started_at = datetime.utcnow()
        mock_job.completed_at = datetime.utcnow()
        mock_job.result = JobResult(success=True, message="Test completed")
        mock_job.result.outputs = outputs
        mock_job.result.data = data

    mock_job.complete_with_outputs = complete_with_outputs

    # Set up job manager with notifier
    job_manager._notifier = mock_notifier

    # Submit job
    job_id = await job_manager.submit_job(mock_job)

    # Wait for job to complete
    task = job_manager._tasks[job_id]
    await task

    # Verify result was saved to database only after completion
    assert mock_record.outputs == outputs
    assert mock_record.data == data
    assert mock_record.status == "completed"
    mock_session.commit.assert_called()

    # Verify notification was sent
    mock_notifier.notify_completion.assert_awaited_once_with(
        job_id=job_id,
        job_type=mock_job.type,
        status=JobStatus.COMPLETED.value,
        message="Test completed",
        outputs=outputs,
        data=data,
        started_at=mock_job.started_at,
        completed_at=mock_job.completed_at,
    )


@pytest.mark.asyncio
async def test_delete_job(job_manager, mock_job, mock_session):
    """Test deleting a job and its database record"""
    # Create a mock record that will be returned by query
    mock_record = mock_session.query.return_value.filter.return_value.first.return_value

    # Submit job
    job_id = await job_manager.submit_job(mock_job)

    # Delete the job
    result = await job_manager.delete_job(job_id)

    # Verify job was deleted
    assert result is True
    assert job_id not in job_manager._running_jobs
    assert job_id not in job_manager._tasks
    mock_session.delete.assert_called_once_with(mock_record)
    mock_session.commit.assert_called()


@pytest.mark.asyncio
async def test_notification_formatting(job_manager, mock_job, mock_session, mock_notifier):
    """Test job notification formatting"""
    # Configure mock job to complete
    mock_job.start = AsyncMock()
    mock_job.start.side_effect = lambda: mock_job.complete_job()

    # Add complete_job method to mock
    def complete_job():
        mock_job.status = JobStatus.COMPLETED
        mock_job.started_at = datetime.utcnow()
        mock_job.completed_at = datetime.utcnow()
        mock_job.result = JobResult(success=True, message="Test completed")

    mock_job.complete_job = complete_job

    # Set up job manager with notifier
    job_manager._notifier = mock_notifier

    job_id = await job_manager.submit_job(mock_job)

    # Wait for job to complete
    task = job_manager._tasks[job_id]
    await task

    # Verify notification format
    mock_notifier.notify_completion.assert_awaited_once_with(
        job_id=job_id,
        job_type=mock_job.type,
        status=JobStatus.COMPLETED.value,
        message="Test completed",
        outputs=[],
        data={},
        started_at=mock_job.started_at,
        completed_at=mock_job.completed_at,
    )


@pytest.mark.asyncio
async def test_list_jobs(job_manager, mock_session):
    """Test listing jobs"""
    # Create mock job records with proper to_dict implementation
    now = datetime.utcnow()
    job_records = [
        Mock(
            spec=JobRecord,
            id="test-job-1",
            type="indexer",
            status=JobStatus.RUNNING.value,
            started_at=now,
            completed_at=None,
            success=None,
            message="Running job 1",
            outputs=["Output 1"],
            created_at=now,
            to_dict=Mock(
                return_value={
                    "id": "test-job-1",
                    "type": "indexer",
                    "status": JobStatus.RUNNING.value,
                    "started_at": now.isoformat(),
                    "completed_at": None,
                    "success": None,
                    "message": "Running job 1",
                }
            ),
        ),
        Mock(
            spec=JobRecord,
            id="test-job-2",
            type="indexer",
            status=JobStatus.COMPLETED.value,
            started_at=now,
            completed_at=now,
            success=True,
            message="Completed job 2",
            outputs=["Output 2.1", "Output 2.2"],
            created_at=now,
            to_dict=Mock(
                return_value={
                    "id": "test-job-2",
                    "type": "indexer",
                    "status": JobStatus.COMPLETED.value,
                    "started_at": now.isoformat(),
                    "completed_at": now.isoformat(),
                    "success": True,
                    "message": "Completed job 2",
                }
            ),
        ),
    ]

    # Configure mock session to return our records
    mock_session.query.return_value.filter.return_value.all.return_value = job_records

    # Test listing all jobs
    jobs = await job_manager.list_jobs()
    assert len(jobs) == 2
    assert jobs[0]["id"] == "test-job-1"
    assert jobs[1]["id"] == "test-job-2"


@pytest.mark.asyncio
async def test_list_jobs_time_filter(job_manager, mock_session):
    """Test listing jobs with time filter"""
    now = datetime.utcnow()

    # Create a mock record with proper to_dict implementation
    mock_record = Mock(
        spec=JobRecord,
        id="current-job",
        type="indexer",
        status=JobStatus.COMPLETED.value,
        started_at=now,
        completed_at=now,
        success=True,
        message="Recent job",
        outputs=["Output 1"],
        created_at=now,
        to_dict=lambda: {
            "id": "current-job",
            "type": "indexer",
            "status": JobStatus.COMPLETED.value,
            "started_at": now.isoformat(),
            "completed_at": now.isoformat(),
            "success": True,
            "message": "Recent job",
        },
    )

    # Configure mock session to return our record
    mock_session.query.return_value.filter.return_value.all.return_value = [mock_record]

    # Test listing jobs with time filter
    jobs = await job_manager.list_jobs()

    # Verify job list
    assert len(jobs) == 1
    assert jobs[0]["id"] == "current-job"
