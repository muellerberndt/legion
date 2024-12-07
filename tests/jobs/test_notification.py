import pytest
from unittest.mock import AsyncMock, patch
from src.jobs.notification import JobNotifier
from src.services.notification_service import NotificationService
from datetime import datetime, timedelta


class MockNotificationService(NotificationService):
    """Mock notification service for testing"""

    def __init__(self):
        self.messages = []
        self._send_message_mock = AsyncMock()

    async def send_message(self, message: str) -> None:
        """Implement the abstract method"""
        self.messages.append(message)
        await self._send_message_mock(message)  # Call the mock for tracking


@pytest.fixture
def mock_service():
    return MockNotificationService()


@pytest.fixture
def notifier():
    # Reset singleton state
    JobNotifier._instance = None
    JobNotifier._notification_services = []
    # Mock TelegramService
    with patch("src.jobs.notification.TelegramService") as mock_telegram:
        mock_telegram.get_instance.return_value = AsyncMock()
        return JobNotifier()


@pytest.mark.asyncio
async def test_register_service(notifier, mock_service):
    """Test registering a notification service"""
    # Register service
    JobNotifier.register_service(mock_service)
    assert mock_service in JobNotifier._notification_services

    # Test duplicate registration
    JobNotifier.register_service(mock_service)
    assert len(JobNotifier._notification_services) == 1


@pytest.mark.asyncio
async def test_notify_completion(notifier, mock_service):
    """Test sending job completion notifications"""
    JobNotifier.register_service(mock_service)

    # Test successful notification
    started = datetime.utcnow()
    completed = started + timedelta(seconds=1)

    await notifier.notify_completion(
        job_id="test-123",
        job_type="test",
        status="completed",
        message="Test completed successfully",
        started_at=started,
        completed_at=completed,
    )

    mock_service._send_message_mock.assert_called_once()
    message = mock_service._send_message_mock.call_args[0][0]

    # Verify message format
    assert "test-123" in message
    assert "test" in message
    assert "completed" in message
    assert "Test completed successfully" in message
    assert "Duration: 1.0s" in message


@pytest.mark.asyncio
async def test_notify_completion_error_handling(notifier, mock_service):
    """Test error handling in notifications"""
    JobNotifier.register_service(mock_service)

    # Make service raise an error
    mock_service._send_message_mock.side_effect = Exception("Test error")

    # Should not raise exception
    await notifier.notify_completion(job_id="test-123", job_type="test", status="failed", message="Test failed")

    mock_service._send_message_mock.assert_called_once()


@pytest.mark.asyncio
async def test_multiple_services(notifier):
    """Test notifications with multiple services"""
    service1 = MockNotificationService()
    service2 = MockNotificationService()

    JobNotifier.register_service(service1)
    JobNotifier.register_service(service2)

    await notifier.notify_completion(job_id="test-123", job_type="test", status="completed", message="Test message")

    service1._send_message_mock.assert_called_once()
    service2._send_message_mock.assert_called_once()

    # Both services should receive the same message
    assert service1._send_message_mock.call_args == service2._send_message_mock.call_args


@pytest.mark.asyncio
async def test_notification_formatting(notifier, mock_service):
    """Test different notification message formats"""
    JobNotifier.register_service(mock_service)

    # Test completion notification
    await notifier.notify_completion(job_id="test-123", job_type="test", status="completed", message="Test completed")
    completion_msg = mock_service._send_message_mock.call_args[0][0]
    assert "🔔" in completion_msg
    assert "completed" in completion_msg

    # Reset mock
    mock_service._send_message_mock.reset_mock()

    # Test failure notification
    await notifier.notify_completion(job_id="test-456", job_type="test", status="failed", message="Test failed")
    failure_msg = mock_service._send_message_mock.call_args[0][0]
    assert "🔔" in failure_msg
    assert "failed" in failure_msg

    # Verify different messages
    assert completion_msg != failure_msg
