import pytest
from unittest.mock import patch, AsyncMock
from src.ai.llm import chat_completion


@pytest.mark.asyncio
async def test_chat_completion_success():
    """Test successful chat completion"""
    # Mock response
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = "Test response"

    # Mock OpenAI client
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    # Test messages
    messages = [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Hello"},
    ]

    with patch("src.ai.llm.AsyncOpenAI", return_value=mock_client):
        response = await chat_completion(messages)
        assert response == "Test response"
        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-4",
            messages=messages,
            temperature=0.1,
        )


@pytest.mark.asyncio
async def test_chat_completion_no_api_key():
    """Test chat completion with missing API key"""

    with patch("src.ai.llm.Config.get", return_value=None):
        with pytest.raises(ValueError, match="OpenAI API key not configured"):
            await chat_completion([{"role": "user", "content": "test"}])


@pytest.mark.asyncio
async def test_chat_completion_custom_model():
    """Test chat completion with custom model"""
    # Mock response
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = "Test response"

    # Mock OpenAI client
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    # Test messages
    messages = [{"role": "user", "content": "Hello"}]
    custom_model = "gpt-3.5-turbo"

    with patch("src.ai.llm.AsyncOpenAI", return_value=mock_client):
        response = await chat_completion(messages, model=custom_model)
        assert response == "Test response"
        mock_client.chat.completions.create.assert_called_once_with(
            model=custom_model,
            messages=messages,
            temperature=0.1,
        )
