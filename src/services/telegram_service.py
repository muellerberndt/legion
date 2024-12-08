from typing import Optional
from src.utils.config import Config
from src.util.logging import Logger
import aiohttp


class TelegramService:
    """Service for sending messages via Telegram"""

    def __init__(self):
        self.config = Config()
        self.logger = Logger(__name__)
        self.base_url = "https://api.telegram.org"
        self._session = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Close the session"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def send_message(self, message: str, chat_id: Optional[str] = None) -> bool:
        """Send a message via Telegram"""
        try:
            token = self.config.get("telegram.bot_token")
            if not token:
                self.logger.error("Telegram bot token not configured")
                return False

            chat_id = chat_id or self.config.get("telegram.chat_id")
            if not chat_id:
                self.logger.error("Telegram chat ID not configured")
                return False

            # Split message if it's too long (Telegram has a 4096 character limit)
            max_length = 4000  # Leave some room for formatting
            messages = [message[i : i + max_length] for i in range(0, len(message), max_length)]

            session = await self._get_session()

            # Send each part
            for msg_part in messages:
                async with session.post(
                    f"{self.base_url}/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": msg_part, "parse_mode": "Markdown"},
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        self.logger.error(f"Telegram API error: {error_text}")
                        return False

            return True

        except Exception as e:
            self.logger.error(f"Error sending Telegram message: {str(e)}")
            return False
