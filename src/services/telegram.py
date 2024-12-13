import telegram
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from typing import Optional
from src.config.config import Config
from src.util.logging import Logger
from src.services.notification_service import NotificationService
import os
import tempfile
from datetime import datetime


class TelegramService(NotificationService):
    """Service for interacting with Telegram"""

    _instance: Optional["TelegramService"] = None
    MAX_MESSAGE_LENGTH = 4096

    def __init__(self):
        self.config = Config()
        self.logger = Logger("TelegramService")
        self.bot_token = self.config.get("telegram", {}).get("bot_token")
        self.chat_id = self.config.get("telegram", {}).get("chat_id")
        self.app = None

        if not self.bot_token:
            raise ValueError("Telegram bot token not configured")

        self.bot = telegram.Bot(token=self.bot_token)

    @classmethod
    def get_instance(cls) -> "TelegramService":
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_app(self, app: Application) -> None:
        """Set the application instance"""
        self.app = app
        self.logger.info("Telegram application instance set")

    def _create_temp_file(self, content: str, prefix: str = "message_") -> str:
        """Create a temporary file with the message content"""
        try:
            # Create temp file with timestamp in name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{prefix}{timestamp}.txt"
            temp_dir = tempfile.gettempdir()
            file_path = os.path.join(temp_dir, filename)

            # Write content to file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            return file_path
        except Exception as e:
            self.logger.error(f"Failed to create temp file: {e}")
            raise

    async def send_message(self, message: str) -> None:
        """Send a message to the configured chat"""
        try:
            self.logger.debug("Checking Telegram service prerequisites...")

            if not self.bot:
                self.logger.error("Bot not initialized")
                raise RuntimeError("Bot not initialized")

            if not self.chat_id:
                self.logger.error("No chat_id configured")
                raise RuntimeError("No chat_id configured")

            self.logger.debug(f"Prerequisites OK. Bot: {bool(self.bot)}, Chat ID: {self.chat_id}")
            self.logger.debug(f"Message length: {len(message)}")

            if len(message) > self.MAX_MESSAGE_LENGTH:
                self.logger.debug("Message exceeds length limit, sending as file...")

                # Create a preview of the message
                preview_length = 1000  # Show first 1000 characters
                preview = message[:preview_length] + "...\n\n(Full content in attached file)"

                # Send preview message
                await self.bot.send_message(chat_id=self.chat_id, text=preview, parse_mode="HTML")

                # Create and send file with full content
                file_path = self._create_temp_file(message)
                try:
                    await self.send_file(file_path, caption="Full message content")
                finally:
                    # Clean up temp file
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        self.logger.error(f"Failed to remove temp file {file_path}: {e}")
            else:
                # Send normal message
                await self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode="HTML")

            self.logger.debug("Message sent successfully")
        except Exception as e:
            self.logger.error(f"Failed to send message: {str(e)}")
            self.logger.debug(f"Bot state: {self.bot}")
            self.logger.debug(f"Chat ID: {self.chat_id}")
            raise

    async def send_file(self, file_path: str, caption: str = None) -> None:
        """Send a file to the configured chat"""
        if not self.bot:
            raise RuntimeError("Bot not initialized")

        try:
            with open(file_path, "rb") as f:
                await self.bot.send_document(
                    chat_id=self.chat_id, document=f, caption=caption, filename=os.path.basename(file_path)
                )
        except Exception as e:
            self.logger.error(f"Failed to send file: {e}")
            raise

    async def start_bot(self):
        """Start the Telegram bot"""
        app = Application.builder().token(self.bot_token).build()
        self.set_app(app)

        # Register handlers
        app.add_handler(CommandHandler("start", self.handle_start))
        app.add_handler(CommandHandler("help", self.handle_help))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        # Start the bot
        await app.run_polling()

    async def handle_start(self, update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        await update.message.reply_text("👋 Welcome to the Security Program Bot!\n" "Use /help to see available commands.")

    async def handle_help(self, update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        await update.message.reply_text(
            "Available commands:\n"
            "/list_projects - List all indexed projects\n"
            "/list_assets - List all downloaded assets\n"
            "You can also chat with me about security programs!"
        )

    async def handle_message(self, update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
        """Handle user messages"""
        # Future: Integrate with LLM for chat functionality
        await update.message.reply_text("I understand you! But LLM integration is coming soon...")
