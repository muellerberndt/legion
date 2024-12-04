import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.jobs.manager import JobManager
from src.jobs.base import Job, JobType, JobStatus, JobResult
from src.backend.database import DBSessionMixin
from datetime import datetime
from src.jobs.notification import JobNotifier

@pytest.fixture
def job_manager():
    manager = JobManager()
    manager._jobs.clear()  # Ensure clean state
    return manager

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
    mock_result.to_dict.return_value = {
        'success': True,
        'message': "Test result",
        'data': {},
        'outputs': []
    }
    job.result = mock_result
    
    # Mock to_dict method
    job.to_dict.return_value = {
        'id': job.id,
        'type': job.type.value,
        'status': job.status.value,
        'started_at': job.started_at.isoformat() if job.started_at else None,
        'completed_at': job.completed_at.isoformat() if job.completed_at else None,
        'result': job.result.to_dict(),
        'error': job.error
    }
    
    # Mock start method
    job.start = AsyncMock()
    
    return job

@pytest.fixture
def mock_session():
    with patch('src.backend.database.DBSessionMixin.get_session') as mock:
        session = Mock()
        session.__enter__ = Mock(return_value=session)
        session.__exit__ = Mock(return_value=None)
        mock.return_value = session
        yield session

@pytest.fixture
def mock_notifier():
    with patch('src.jobs.notification.JobNotifier') as mock:
        notifier = Mock()
        notifier.notify_completion = AsyncMock()
        mock.return_value = notifier
        yield notifier

@pytest.mark.asyncio
async def test_submit_job(job_manager, mock_job, mock_session, mock_notifier):
    """Test submitting a job with notifications"""
    job_id = await job_manager.submit_job(mock_job)
    assert job_id == mock_job.id
    assert mock_job.id in job_manager._jobs
    
    # Verify database record was created
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
    
    # Verify notification was sent
    mock_notifier.notify_completion.assert_called_once()
    call_args = mock_notifier.notify_completion.call_args[1]
    assert call_args['job_id'] == job_id
    assert call_args['status'] == mock_job.status.value
    assert call_args['message'] == mock_job.result.message

@pytest.mark.asyncio
async def test_job_lifecycle(job_manager, mock_job, mock_session, mock_notifier):
    """Test complete job lifecycle with status changes"""
    # Submit job
    job_id = await job_manager.submit_job(mock_job)
    
    # Verify initial state
    assert mock_job.status == JobStatus.PENDING
    
    # Simulate job starting
    mock_job.status = JobStatus.RUNNING
    mock_job.started_at = datetime.utcnow()
    
    # Simulate job completion
    mock_job.status = JobStatus.COMPLETED
    mock_job.completed_at = datetime.utcnow()
    mock_job.result.message = "Job completed successfully"
    
    # Update job status
    await job_manager.update_job_status(job_id, JobStatus.COMPLETED)
    
    # Verify final notification
    mock_notifier.notify_completion.assert_called()
    call_args = mock_notifier.notify_completion.call_args[1]
    assert call_args['status'] == JobStatus.COMPLETED.value
    assert call_args['message'] == "Job completed successfully"
    assert call_args['started_at'] == mock_job.started_at
    assert call_args['completed_at'] == mock_job.completed_at

@pytest.mark.asyncio
async def test_job_failure(job_manager, mock_job, mock_session, mock_notifier):
    """Test job failure handling"""
    job_id = await job_manager.submit_job(mock_job)
    
    # Simulate job failure
    error_msg = "Test error occurred"
    mock_job.status = JobStatus.FAILED
    mock_job.error = error_msg
    mock_job.result = None
    
    # Update job status
    await job_manager.update_job_status(job_id, JobStatus.FAILED)
    
    # Verify failure notification
    mock_notifier.notify_completion.assert_called()
    call_args = mock_notifier.notify_completion.call_args[1]
    assert call_args['status'] == JobStatus.FAILED.value
    assert call_args['message'] == error_msg

@pytest.mark.asyncio
async def test_job_cancellation(job_manager, mock_job, mock_session, mock_notifier):
    """Test job cancellation"""
    # Set up mock job
    mock_job.stop = AsyncMock()
    mock_job.status = JobStatus.RUNNING  # Start with running status
    job_manager._jobs[mock_job.id] = mock_job
    
    # Cancel the job
    success = await job_manager.stop_job(mock_job.id)
    assert success
    
    # Verify job was stopped and status updated
    mock_job.stop.assert_called_once()
    assert mock_job.status == JobStatus.CANCELLED
    
    # Verify cancellation notification
    mock_notifier.notify_completion.assert_called()
    call_args = mock_notifier.notify_completion.call_args[1]
    assert call_args['status'] == JobStatus.CANCELLED.value

@pytest.mark.asyncio
async def test_concurrent_jobs(job_manager, mock_session, mock_notifier):
    """Test handling multiple concurrent jobs"""
    jobs = []
    for i in range(3):
        job = Mock(spec=Job)
        job.id = f"test-job-{i}"
        job.type = JobType.INDEXER
        job.status = JobStatus.PENDING
        job.error = None
        job.started_at = None
        job.completed_at = None
        job.start = AsyncMock()
        
        # Set up result
        result = Mock(spec=JobResult)
        result.success = True
        result.message = f"Job {i} completed"
        result.outputs = []
        result.data = {}
        result.to_dict.return_value = {
            'success': True,
            'message': result.message,
            'data': {},
            'outputs': []
        }
        job.result = result
        
        # Set up to_dict
        job.to_dict.return_value = {
            'id': job.id,
            'type': job.type.value,
            'status': job.status.value,
            'started_at': None,
            'completed_at': None,
            'result': result.to_dict(),
            'error': None
        }
        
        jobs.append(job)
    
    # Submit all jobs
    job_ids = []
    for job in jobs:
        job_id = await job_manager.submit_job(job)
        job_ids.append(job_id)
    
    # Verify all jobs were registered
    assert len(job_manager._jobs) == len(jobs)
    
    # Verify notifications for each job
    assert mock_notifier.notify_completion.call_count == len(jobs)

def test_list_jobs(job_manager, mock_job):
    """Test listing jobs with filters"""
    job_manager._jobs[mock_job.id] = mock_job
    
    # List all jobs
    jobs = job_manager.list_jobs()
    assert len(jobs) == 1
    assert jobs[0]['id'] == mock_job.id
    
    # Test filtering by type
    jobs = job_manager.list_jobs(job_type=JobType.INDEXER)
    assert len(jobs) == 1
    jobs = job_manager.list_jobs(job_type=JobType.AGENT)
    assert len(jobs) == 0