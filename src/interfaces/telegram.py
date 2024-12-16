import asyncio
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from src.interfaces.base import Interface
from src.actions.registry import ActionRegistry
from src.util.logging import Logger
from src.config.config import Config
from src.services.telegram import TelegramService
from src.ai.chatbot import Chatbot
import shlex
import telegram


class TelegramInterface(Interface):
    """Telegram bot interface"""

    def __init__(self, action_registry: ActionRegistry):
        super().__init__()
        self.logger = Logger("TelegramInterface")
        self.action_registry = action_registry
        self.app = None
        self.service = TelegramService.get_instance()
        self._agents = {}  # Session ID -> Chat
        self._polling_task = None
        self._initialized = False

    def _parse_command_args(self, message: str) -> list:
        """Parse command arguments, preserving quoted strings"""
        try:
            # Split into command and args
            parts = message.split(None, 1)
            if len(parts) < 2:
                return []  # No arguments

            args_str = parts[1]
            # For single argument that looks like JSON, return as is without stripping quotes
            if args_str.startswith("{") and args_str.endswith("}"):
                return [args_str]

            # For quoted strings, strip quotes and return as single arg
            if (args_str.startswith("'") and args_str.endswith("'")) or (args_str.startswith('"') and args_str.endswith('"')):
                return [args_str[1:-1]]

            # Otherwise use shlex to parse
            return shlex.split(args_str)
        except ValueError as e:
            self.logger.error(f"Error parsing arguments: {str(e)}")
            # Return raw split as fallback
            return args_str.split()
        except IndexError:
            return []  # No arguments provided

    def _create_command_handler(self, command_name: str, action_handler):
        """Create a command handler function for a specific command"""

        async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            try:
                # Parse arguments from the full message text
                args = self._parse_command_args(update.message.text)

                # Execute the action with the arguments
                if args:
                    result = await action_handler(*args)
                else:
                    result = await action_handler()

                if result:
                    # Convert result to string
                    if hasattr(result, "content"):
                        content = result.content
                    else:
                        content = str(result)

                    # Use TelegramService to handle message sending with proper size handling
                    service = TelegramService.get_instance()
                    service.chat_id = str(update.message.chat.id)
                    await service.send_message(content)

            except Exception as e:
                self.logger.error(f"Error executing command {command_name}: {e}")
                error_msg = f"Error executing command: {str(e)}"
                service = TelegramService.get_instance()
                service.chat_id = str(update.message.chat.id)
                await service.send_message(error_msg)

        return handler

    async def start(self) -> None:
        """Start the Telegram bot"""
        if self._initialized:
            self.logger.warning("Telegram interface already initialized")
            return

        try:
            config = Config()
            token = config.get("telegram", {}).get("bot_token")
            if not token:
                raise ValueError("Telegram bot token not configured")

            # Build application with request timeout settings
            self.app = (
                Application.builder()
                .token(token)
                .connect_timeout(60)  # Increased timeouts
                .read_timeout(60)
                .write_timeout(60)
                .get_updates_connect_timeout(60)
                .get_updates_read_timeout(60)
                .get_updates_write_timeout(60)
                .build()
            )

            # Register handlers
            await self._register_handlers()

            # Initialize the application
            await self.app.initialize()

            # Start the bot
            await self.app.start()

            # Register commands
            await self._register_commands()

            # Update service with app instance
            self.service.set_app(self.app)

            # Start polling in background without blocking
            self._polling_task = asyncio.create_task(
                self.app.updater.start_polling(
                    drop_pending_updates=True,  # Drop pending updates on startup
                    poll_interval=2.0,  # Increased poll interval to reduce load
                    timeout=60,  # Increased timeout
                    bootstrap_retries=-1,  # Infinite retries with exponential backoff
                    read_timeout=60,
                    write_timeout=60,
                    connect_timeout=60,
                    allowed_updates=Update.ALL_TYPES,
                    error_callback=self._handle_error,
                )
            )

            self._initialized = True
            self.logger.info("Telegram interface started")

        except Exception as e:
            self.logger.error(f"Failed to start Telegram interface: {e}")
            await self.stop()  # Clean up on failure
            raise

    async def _register_handlers(self) -> None:
        """Register message handlers"""
        # Register start command first
        self.app.add_handler(CommandHandler("start", self._handle_start_command))

        # Register other command handlers
        for name, (handler, spec) in self.action_registry.get_actions().items():
            self.app.add_handler(CommandHandler(name, self._create_command_handler(name, handler)))

        # Register message handler for non-commands
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))

    async def _register_commands(self) -> None:
        """Register bot commands with Telegram"""
        try:
            commands = []
            for name, (_, spec) in self.action_registry.get_actions().items():
                # Get description and truncate to 256 chars if needed
                description = spec.description if spec.description else "No description available"
                if len(description) > 256:
                    description = description[:253] + "..."

                commands.append(BotCommand(name, description))

            await self.app.bot.set_my_commands(commands)
            self.logger.info(f"Registered {len(commands)} commands with Telegram")

        except Exception as e:
            self.logger.error(f"Failed to register commands: {e}")

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Internal handler for Telegram messages"""
        await self.handle_message(update.message.text, str(update.message.chat.id))

    async def handle_message(self, content: str, session_id: str) -> None:
        """Handle a non-command message through the conversation agent"""
        try:
            # Get or create conversation agent for this session
            if session_id not in self._agents:
                self._agents[session_id] = Chatbot()

            agent = self._agents[session_id]
            response = await agent.process_message(content)
            await self.send_message(response, session_id)

        except Exception as e:
            self.logger.error(f"Error in conversation: {e}")
            await self.send_message(f"Sorry, I encountered an error: {str(e)}", session_id)

    async def send_message(self, content: str, session_id: str) -> None:
        """Send a message to a specific chat"""
        if not self.app or not self.app.bot:
            self.logger.error("Bot not initialized")
            return
        try:
            # Use TelegramService to handle message sending with proper size handling
            service = TelegramService.get_instance()
            service.chat_id = session_id  # Set the target chat ID
            await service.send_message(content)

        except Exception as e:
            self.logger.error(f"Failed to send message: {e}")
            raise

    async def stop(self) -> None:
        """Stop the interface"""
        self.logger.info("Stopping Telegram interface...")

        try:
            # Cancel polling task
            if self._polling_task:
                self._polling_task.cancel()
                try:
                    await self._polling_task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    self.logger.error(f"Error cancelling polling task: {e}")
                self._polling_task = None

            # Stop application
            if self.app:
                try:
                    await self.app.stop()
                    await self.app.shutdown()
                except Exception as e:
                    self.logger.error(f"Error stopping application: {e}")
                self.app = None

            # Clear state
            self._agents.clear()
            self._initialized = False

            self.logger.info("Telegram interface stopped")

        except Exception as e:
            self.logger.error(f"Error during Telegram interface shutdown: {e}")
            raise

    def _handle_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors during polling"""
        try:
            if isinstance(context.error, telegram.error.NetworkError):
                self.logger.warning(
                    "Network error in Telegram polling - will retry automatically",
                    extra_data={"error": str(context.error), "update": str(update) if update else None},
                )
            elif isinstance(context.error, telegram.error.TimedOut):
                self.logger.warning(
                    "Timeout in Telegram polling - will retry automatically",
                    extra_data={"error": str(context.error), "update": str(update) if update else None},
                )
            elif isinstance(context.error, telegram.error.RetryAfter):
                # Rate limit error - log the retry delay
                retry_in = context.error.retry_after if hasattr(context.error, "retry_after") else 30
                self.logger.warning(
                    f"Rate limited by Telegram - retrying in {retry_in} seconds",
                    extra_data={"retry_after": retry_in, "update": str(update) if update else None},
                )
            else:
                self.logger.error(
                    "Error in Telegram polling",
                    extra_data={
                        "error": str(context.error),
                        "error_type": type(context.error).__name__,
                        "update": str(update) if update else None,
                    },
                )
        except Exception as e:
            self.logger.error(f"Error in error handler: {e}")

    async def _handle_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /start command"""
        welcome_message = "gm 👋\n" "How can I be of service today?"
        await update.message.reply_text(welcome_message)
