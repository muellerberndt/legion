"""OpenAI LLM interaction utilities"""

from typing import List, Dict
from openai import AsyncOpenAI
from src.config.config import Config


async def chat_completion(messages: List[Dict[str, str]], model: str = None, temperature: float = 0.1) -> str:
    """Simple wrapper for OpenAI chat completion

    Args:
        messages: List of message dictionaries with 'role' and 'content'
        model: Optional model override
        temperature: Optional temperature override

    Returns:
        The response content from the model
    """
    config = Config()
    api_key = config.llm_api_key
    base_url = config.llm_base_url

    if not api_key:
        raise ValueError("LLM API key not configured")

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    model = model or config.llm_model

    response = await client.chat.completions.create(model=model, messages=messages, temperature=temperature)

    return response.choices[0].message.content
