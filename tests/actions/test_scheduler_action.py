"""Tests for the scheduler action"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from src.actions.scheduler import SchedulerAction
from src.jobs.scheduler import Scheduler


@pytest.fixture
def mock_scheduler():
    """Create mock scheduler with some test actions"""
    scheduler = Mock(spec=Scheduler)

    # Mock list_actions
    scheduler.list_actions.return_value = {
        "test_action": {
            "name": "test_action",
            "command": "test_command",
            "enabled": True,
            "interval_minutes": 60,
            "last_run": datetime.utcnow().isoformat(),
            "next_run": (datetime.utcnow()).isoformat(),
        },
        "disabled_action": {
            "name": "disabled_action",
            "command": "another_command",
            "enabled": False,
            "interval_minutes": 30,
            "last_run": None,
            "next_run": None,
        },
    }

    # Mock enable/disable
    scheduler.enable_action.return_value = True
    scheduler.disable_action.return_value = True
    scheduler.get_action_status.side_effect = lambda name: scheduler.list_actions().get(name)

    return scheduler


@pytest.fixture
async def action():
    """Create scheduler action with mocked scheduler"""
    return SchedulerAction()


@pytest.mark.asyncio
async def test_list_command(action, mock_scheduler):
    """Test listing scheduled actions"""
    with patch("src.jobs.scheduler.Scheduler.get_instance", return_value=mock_scheduler):
        result = await action.execute("list")

        assert "📅 Scheduled Actions:" in result
        assert "test_action" in result
        assert "disabled_action" in result
        assert "✅" in result  # Enabled action indicator
        assert "❌" in result  # Disabled action indicator
        assert "60 minutes" in result
        assert "30 minutes" in result


@pytest.mark.asyncio
async def test_enable_command(action, mock_scheduler):
    """Test enabling an action"""
    with patch("src.jobs.scheduler.Scheduler.get_instance", return_value=mock_scheduler):
        result = await action.execute("enable", "test_action")
        assert "✅ Enabled scheduled action: test_action" in result
        mock_scheduler.enable_action.assert_called_once_with("test_action")

        # Test with non-existent action
        mock_scheduler.enable_action.return_value = False
        result = await action.execute("enable", "nonexistent")
        assert "❌ Action not found: nonexistent" in result


@pytest.mark.asyncio
async def test_disable_command(action, mock_scheduler):
    """Test disabling an action"""
    with patch("src.jobs.scheduler.Scheduler.get_instance", return_value=mock_scheduler):
        result = await action.execute("disable", "test_action")
        assert "✅ Disabled scheduled action: test_action" in result
        mock_scheduler.disable_action.assert_called_once_with("test_action")

        # Test with non-existent action
        mock_scheduler.disable_action.return_value = False
        result = await action.execute("disable", "nonexistent")
        assert "❌ Action not found: nonexistent" in result


@pytest.mark.asyncio
async def test_status_command(action, mock_scheduler):
    """Test getting action status"""
    with patch("src.jobs.scheduler.Scheduler.get_instance", return_value=mock_scheduler):
        result = await action.execute("status", "test_action")

        assert "📊 Status for test_action:" in result
        assert "Command: test_command" in result
        assert "Enabled: Yes" in result
        assert "60 minutes" in result
        assert "Last run:" in result
        assert "Next run:" in result

        # Test with non-existent action
        result = await action.execute("status", "nonexistent")
        assert "❌ Action not found: nonexistent" in result


@pytest.mark.asyncio
async def test_invalid_command(action, mock_scheduler):
    """Test handling invalid command"""
    with patch("src.jobs.scheduler.Scheduler.get_instance", return_value=mock_scheduler):
        result = await action.execute("invalid")
        assert "Unknown command: invalid. Use /help scheduler for usage information." in result


@pytest.mark.asyncio
async def test_missing_action_name(action, mock_scheduler):
    """Test commands that require action name but none provided"""
    with patch("src.jobs.scheduler.Scheduler.get_instance", return_value=mock_scheduler):
        result = await action.execute("enable")
        assert "Please specify an action name" in result

        result = await action.execute("disable")
        assert "Please specify an action name" in result

        result = await action.execute("status")
        assert "Please specify an action name" in result


@pytest.mark.asyncio
async def test_no_command(action, mock_scheduler):
    """Test executing without command"""
    with patch("src.jobs.scheduler.Scheduler.get_instance", return_value=mock_scheduler):
        result = await action.execute()
        assert "Please specify a command" in result


@pytest.mark.asyncio
async def test_error_handling(action, mock_scheduler):
    """Test error handling"""
    with patch("src.jobs.scheduler.Scheduler.get_instance", return_value=mock_scheduler):
        # Simulate an error in scheduler
        mock_scheduler.list_actions.side_effect = Exception("Test error")

        result = await action.execute("list")
        assert "Error executing scheduler command: Test error" in result
