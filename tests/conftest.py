import pytest
from src.config.config import Config


@pytest.fixture(autouse=True)
def enable_test_mode():
    """Enable test mode for all tests."""
    Config.set_test_mode(True)
    yield
    Config.set_test_mode(False)  # Reset after test
