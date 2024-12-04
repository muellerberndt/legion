import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.jobs.manager import JobManager
from src.jobs.base import Job, JobType, JobStatus, JobResult
from src.backend.database import DBSessionMixin
from datetime import datetime

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
    return job

@pytest.fixture
def mock_session():
    with patch('src.backend.database.DBSessionMixin.get_session') as mock:
        session = Mock()
        session.__enter__ = Mock(return_value=session)
        session.__exit__ = Mock(return_value=None)
        mock.return_value = session
        yield session

@pytest.mark.asyncio
async def test_submit_job(job_manager, mock_job, mock_session):
    job_id = await job_manager.submit_job(mock_job)
    assert job_id == mock_job.id
    assert mock_job.id in job_manager._jobs
    
    # Verify database record was created
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()

@pytest.mark.asyncio
async def test_stop_job(job_manager, mock_job):
    mock_job.status = JobStatus.RUNNING
    mock_job.stop = AsyncMock()
    job_manager._jobs[mock_job.id] = mock_job
    
    success = await job_manager.stop_job(mock_job.id)
    
    assert success
    mock_job.stop.assert_called_once()
    assert mock_job.status == JobStatus.CANCELLED

def test_list_jobs(job_manager, mock_job):
    job_manager._jobs[mock_job.id] = mock_job
    
    jobs = job_manager.list_jobs()
    assert len(jobs) == 1
    assert jobs[0]['id'] == mock_job.id
    
    # Test filtering by type
    jobs = job_manager.list_jobs(job_type=JobType.INDEXER)
    assert len(jobs) == 1
    jobs = job_manager.list_jobs(job_type=JobType.AGENT)
    assert len(jobs) == 0