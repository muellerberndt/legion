import telegram
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from typing import Optional
from src.config.config import Config
from src.util.logging import Logger
from src.services.notification_service import NotificationService


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

    async def send_message(self, message: str, chat_id: Optional[str] = None) -> None:
        """Send a message through Telegram"""
        try:
            target_chat = chat_id or self.chat_id
            if not target_chat:
                raise ValueError("No chat ID configured")

            # Split message if it's too long
            if len(message) > self.MAX_MESSAGE_LENGTH:
                chunks = [message[i : i + self.MAX_MESSAGE_LENGTH] for i in range(0, len(message), self.MAX_MESSAGE_LENGTH)]
                for chunk in chunks:
                    await self.bot.send_message(chat_id=target_chat, text=chunk)
            else:
                await self.bot.send_message(chat_id=target_chat, text=message)

        except Exception as e:
            self.logger.error(f"Failed to send Telegram message: {e}")
            raise

    async def send_file(
        self, file_path: str, caption: Optional[str] = None, filename: Optional[str] = None, chat_id: Optional[str] = None
    ) -> None:
        """Send a file through Telegram"""
        try:
            target_chat = chat_id or self.chat_id
            if not target_chat:
                raise ValueError("No chat ID configured")

            # Open and send the file
            with open(file_path, "rb") as f:
                await self.bot.send_document(chat_id=target_chat, document=f, filename=filename, caption=caption)

        except Exception as e:
            self.logger.error(f"Failed to send file via Telegram: {e}")
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
