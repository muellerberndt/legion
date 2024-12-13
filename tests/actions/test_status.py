"""Tests for the status action"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from src.actions.status import StatusAction
from src.jobs.scheduler import Scheduler
from src.jobs.manager import JobManager
from src.webhooks.server import WebhookServer


@pytest.fixture
def mock_job_manager():
    """Create mock job manager with test jobs"""
    manager = Mock(spec=JobManager)
    manager.list_jobs.return_value = [
        {
            "id": "test-job-1",
            "type": "test",
            "status": "running",
            "created_at": datetime.utcnow().isoformat(),
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "success": None,
            "message": None,
        },
        {
            "id": "test-job-2",
            "type": "another_test",
            "status": "completed",
            "created_at": datetime.utcnow().isoformat(),
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
            "success": True,
            "message": "Success",
        },
    ]
    return manager


@pytest.fixture
def mock_scheduler():
    """Create mock scheduler with test actions"""
    scheduler = Mock(spec=Scheduler)
    scheduler.list_actions.return_value = {
        "test_action": {
            "name": "test_action",
            "command": "test_command",
            "enabled": True,
            "interval_minutes": 60,
            "last_run": datetime.utcnow().isoformat(),
            "next_run": datetime.utcnow().isoformat(),
        }
    }
    return scheduler


@pytest.fixture
def mock_webhook_server():
    """Create mock webhook server"""
    server = Mock()
    server.runner = True  # Indicates server is running
    server.port = 8080
    return server


@pytest.mark.asyncio
async def test_status_running_jobs(mock_job_manager, mock_scheduler, mock_webhook_server):
    """Test status shows running jobs"""
    with (
        patch("src.jobs.manager.JobManager.get_instance", return_value=mock_job_manager),
        patch("src.jobs.scheduler.Scheduler.get_instance", return_value=mock_scheduler),
        patch("src.webhooks.server.WebhookServer.get_instance", return_value=mock_webhook_server),
    ):
        action = StatusAction()
        result = await action.execute()

        assert "🏃 Running Jobs:" in result
        assert "test-job-1" in result
        assert "test" in result
        assert "running" in result


@pytest.mark.asyncio
async def test_status_no_running_jobs(mock_job_manager, mock_scheduler, mock_webhook_server):
    """Test status when no jobs are running"""
    mock_job_manager.list_jobs.return_value = []
    with (
        patch("src.jobs.manager.JobManager.get_instance", return_value=mock_job_manager),
        patch("src.jobs.scheduler.Scheduler.get_instance", return_value=mock_scheduler),
        patch("src.webhooks.server.WebhookServer.get_instance", return_value=mock_webhook_server),
    ):
        action = StatusAction()
        result = await action.execute()

        assert "No jobs currently running" in result


@pytest.mark.asyncio
async def test_status_scheduled_actions(mock_job_manager, mock_scheduler, mock_webhook_server):
    """Test status shows scheduled actions"""
    with (
        patch("src.jobs.manager.JobManager.get_instance", return_value=mock_job_manager),
        patch("src.jobs.scheduler.Scheduler.get_instance", return_value=mock_scheduler),
        patch("src.webhooks.server.WebhookServer.get_instance", return_value=mock_webhook_server),
    ):
        action = StatusAction()
        result = await action.execute()

        assert "📅 Scheduled Actions:" in result
        assert "test_action" in result
        assert "test_command" in result
        assert "60 minutes" in result


@pytest.mark.asyncio
async def test_status_no_scheduled_actions(mock_job_manager, mock_scheduler, mock_webhook_server):
    """Test status when no actions are scheduled"""
    mock_scheduler.list_actions.return_value = {}
    with (
        patch("src.jobs.manager.JobManager.get_instance", return_value=mock_job_manager),
        patch("src.jobs.scheduler.Scheduler.get_instance", return_value=mock_scheduler),
        patch("src.webhooks.server.WebhookServer.get_instance", return_value=mock_webhook_server),
    ):
        action = StatusAction()
        result = await action.execute()

        assert "No scheduled actions configured" in result


@pytest.mark.asyncio
async def test_status_webhook_server(mock_job_manager, mock_scheduler, mock_webhook_server):
    """Test status shows webhook server status"""
    with (
        patch("src.jobs.manager.JobManager.get_instance", return_value=mock_job_manager),
        patch("src.jobs.scheduler.Scheduler.get_instance", return_value=mock_scheduler),
        patch("src.webhooks.server.WebhookServer.get_instance", return_value=mock_webhook_server),
    ):
        action = StatusAction()
        result = await action.execute()

        assert "🌐 Webhook Server:" in result
        assert "Running on port 8080" in result


@pytest.mark.asyncio
async def test_status_webhook_server_not_running(mock_job_manager, mock_scheduler, mock_webhook_server):
    """Test status when webhook server is not running"""
    mock_webhook_server.runner = None
    with (
        patch("src.jobs.manager.JobManager.get_instance", return_value=mock_job_manager),
        patch("src.jobs.scheduler.Scheduler.get_instance", return_value=mock_scheduler),
        patch("src.webhooks.server.WebhookServer.get_instance", return_value=mock_webhook_server),
    ):
        action = StatusAction()
        result = await action.execute()

        assert "Not running" in result


@pytest.mark.asyncio
async def test_status_error_handling(mock_job_manager, mock_scheduler, mock_webhook_server):
    """Test error handling in status action"""
    mock_job_manager.list_jobs.side_effect = Exception("Test error")
    with (
        patch("src.jobs.manager.JobManager.get_instance", return_value=mock_job_manager),
        patch("src.jobs.scheduler.Scheduler.get_instance", return_value=mock_scheduler),
        patch("src.webhooks.server.WebhookServer.get_instance", return_value=mock_webhook_server),
    ):
        action = StatusAction()
        result = await action.execute()

        assert "Error getting jobs: Test error" in result
