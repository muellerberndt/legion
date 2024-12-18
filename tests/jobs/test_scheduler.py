"""Tests for the scheduler"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.jobs.scheduler import Scheduler, ScheduledAction
from src.actions.registry import ActionRegistry


@pytest.fixture
def mock_action_registry():
    """Create mock action registry with test actions"""
    registry = Mock(spec=ActionRegistry)
    registry.get_action.return_value = (AsyncMock(), "Test action description")
    return registry


@pytest.fixture
def scheduler(mock_action_registry):
    """Create scheduler instance with mocked dependencies"""
    scheduler = Scheduler()
    scheduler._action_registry = mock_action_registry
    return scheduler


@pytest.fixture
def mock_config():
    """Create mock config with test actions"""
    config = Mock()
    config.get.return_value = {
        "test_action": {"command": "test_command arg1", "interval_minutes": 60, "enabled": True},
        "another_action": {"command": "another_command", "interval_minutes": 30, "enabled": False},
    }
    return config


def test_load_config(scheduler, mock_config):
    """Test loading scheduled actions from config"""
    with patch("src.jobs.scheduler.Config", return_value=mock_config):
        scheduler.config = mock_config
        scheduler.load_config()
        assert len(scheduler.scheduled_actions) == 2
        assert "test_action" in scheduler.scheduled_actions
        assert "another_action" in scheduler.scheduled_actions


@pytest.mark.asyncio
async def test_schedule_action(scheduler):
    """Test scheduling a new action"""
    scheduler.schedule_action("test", "test_command", 60)
    assert "test" in scheduler.scheduled_actions
    action = scheduler.scheduled_actions["test"]
    assert action.command == "test_command"
    assert action.interval_minutes == 60
    assert action.enabled is True


@pytest.mark.asyncio
async def test_enable_disable_action(scheduler):
    """Test enabling and disabling actions"""
    # Schedule an action
    scheduler.schedule_action("test", "test_command", 60, enabled=False)

    # Enable it
    assert scheduler.enable_action("test") is True
    assert scheduler.scheduled_actions["test"].enabled is True

    # Disable it
    assert scheduler.disable_action("test") is True
    assert scheduler.scheduled_actions["test"].enabled is False

    # Test with non-existent action
    assert scheduler.enable_action("nonexistent") is False
    assert scheduler.disable_action("nonexistent") is False


@pytest.mark.asyncio
async def test_start_stop(scheduler):
    """Test starting and stopping the scheduler"""
    # Schedule some actions
    scheduler.schedule_action("test1", "command1", 60)
    scheduler.schedule_action("test2", "command2", 30)

    # Start scheduler
    await scheduler.start()
    assert scheduler._running is True

    # Stop scheduler
    await scheduler.stop()
    assert scheduler._running is False

    # Verify all tasks are cleaned up
    assert not any(action._task for action in scheduler.scheduled_actions.values())


@pytest.mark.asyncio
async def test_list_actions(scheduler):
    """Test listing all actions"""
    # Schedule some actions
    scheduler.schedule_action("test1", "command1", 60)
    scheduler.schedule_action("test2", "command2", 30, enabled=False)

    actions = scheduler.list_actions()
    assert len(actions) == 2
    assert "test1" in actions
    assert "test2" in actions
    assert actions["test1"]["enabled"] is True
    assert actions["test2"]["enabled"] is False


@pytest.mark.asyncio
async def test_run_action(scheduler, mock_action_registry):
    """Test running an action"""
    action = ScheduledAction("test", "test_command arg1", 60)
    await scheduler._run_action(action)

    # Verify action was executed
    handler = mock_action_registry.get_action.return_value[0]
    handler.assert_called_once_with("arg1")
    assert action.last_run is not None
