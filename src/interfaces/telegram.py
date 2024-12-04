import asyncio
from telegram import Bot, Update, Message, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from src.interfaces.base import Interface
from src.actions.registry import ActionRegistry
from src.jobs.notification import NotificationService
from src.util.logging import Logger
from src.config.config import Config
from src.jobs.agent import ConversationAgent

class TelegramInterface(Interface):
    """Telegram bot interface"""
    
    def __init__(self, action_registry: ActionRegistry):
        super().__init__()
        self.logger = Logger("TelegramInterface")
        self.action_registry = action_registry
        self.app = None
        self.service = TelegramService.get_instance()
        self._agents = {}  # Session ID -> ConversationAgent
        self._polling_task = None
        
    async def start(self) -> None:
        """Start the Telegram bot"""
        try:
            config = Config()
            token = config.get('telegram', {}).get('bot_token')
            if not token:
                raise ValueError("Telegram bot token not configured")
            
            # Build application
            self.app = Application.builder().token(token).build()
            
            # Register handlers
            await self._register_handlers()
            
            # Initialize the application
            await self.app.initialize()
            
            # Start the bot
            await self.app.start()
            
            # Register commands
            await self._register_commands()
            
            # Start polling in background without blocking
            self._polling_task = asyncio.create_task(
                self.app.updater.start_polling(
                    poll_interval=0.5,
                    timeout=10,
                    bootstrap_retries=-1,
                    read_timeout=2,
                    write_timeout=2,
                    connect_timeout=2,
                    allowed_updates=Update.ALL_TYPES
                )
            )
            
            self.logger.info("Telegram interface started")
            
        except Exception as e:
            self.logger.error(f"Failed to start Telegram interface: {e}")
            raise
            
    async def _register_handlers(self) -> None:
        """Register message handlers"""
        # Register command handlers
        for name, (handler, spec) in self.action_registry.get_actions().items():
            self.app.add_handler(
                CommandHandler(name, self._create_command_handler(name, handler))
            )
            
        # Register message handler for non-commands
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )
            
    async def _register_commands(self) -> None:
        """Register bot commands with Telegram"""
        try:
            commands = []
            for name, (_, spec) in self.action_registry.get_actions().items():
                # Get description and truncate to 256 chars if needed
                description = spec.description if spec.description else 'No description available'
                if len(description) > 256:
                    description = description[:253] + "..."
                    
                commands.append(BotCommand(name, description))
                
            await self.app.bot.set_my_commands(commands)
            self.logger.info(f"Registered {len(commands)} commands with Telegram")
            
        except Exception as e:
            self.logger.error(f"Failed to register commands: {e}")
            
    def _create_command_handler(self, command_name: str, action_handler):
        """Create a command handler function for a specific command"""
        async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            try:
                # Create message object for action
                from src.interfaces.base import Message as BaseMessage
                action_message = BaseMessage(
                    session_id=str(update.message.chat.id),
                    content=command_name,
                    arguments=context.args  # Args are already strings
                )
                
                # Execute the action
                result = await action_handler(action_message, *context.args)
                
                if result:
                    # Handle ActionResult objects
                    if hasattr(result, 'content'):
                        content = result.content
                    else:
                        content = str(result)
                        
                    await update.message.reply_text(
                        text=content,
                        parse_mode='HTML'
                    )
            except Exception as e:
                self.logger.error(f"Error executing command {command_name}: {e}")
                await update.message.reply_text(
                    text=f"Error executing command: {str(e)}"
                )
        return handler
            
    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Internal handler for Telegram messages"""
        await self.handle_message(update.message.text, str(update.message.chat.id))
            
    async def handle_message(self, content: str, session_id: str) -> None:
        """Handle a non-command message through the conversation agent"""
        try:
            # Get or create conversation agent for this session
            if session_id not in self._agents:
                self._agents[session_id] = ConversationAgent(session_id)
            
            agent = self._agents[session_id]
            response = await agent.process_message(content)
            await self.send_message(response, session_id)
            
        except Exception as e:
            self.logger.error(f"Error in conversation: {e}")
            await self.send_message(
                f"Sorry, I encountered an error: {str(e)}",
                session_id
            )
            
    async def send_message(self, content: str, session_id: str) -> None:
        """Send a message to a specific chat"""
        if not self.app or not self.app.bot:
            self.logger.error("Bot not initialized")
            return
            
        try:
            await self.app.bot.send_message(
                chat_id=session_id,
                text=content,
                parse_mode='HTML'
            )
        except Exception as e:
            self.logger.error(f"Failed to send message: {e}")
            
    async def stop(self) -> None:
        """Stop the interface"""
        self.logger.info("Stopping Telegram interface...")
        
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
        
        if self.app:
            await self.app.stop()
            await self.app.shutdown()
            self.app = None
            
        self.logger.info("Telegram interface stopped")

class TelegramService(NotificationService):
    """Telegram notification service singleton"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TelegramService, cls).__new__(cls)
            cls._instance.initialize()
        return cls._instance
    
    def initialize(self):
        self.logger = Logger("TelegramService")
        self.app = None
        
    @classmethod
    def get_instance(cls):
        return cls()
        
    def set_bot(self, app: Application):
        self.app = app
        
    async def send_message(self, content: str, session_id: str = None) -> None:
        """Send a message through the notification service"""
        if not self.app or not self.app.bot:
            self.logger.error("Bot not initialized")
            return
            
        try:
            config = Config()
            default_chat_id = config.get('telegram', {}).get('chat_id')
            target_chat_id = session_id or default_chat_id
            
            if not target_chat_id:
                self.logger.error("No chat ID configured or provided")
                return
                
            await self.app.bot.send_message(
                chat_id=target_chat_id,
                text=content,
                parse_mode='HTML'
            )
            
        except Exception as e:
            self.logger.error(f"Failed to send notification: {e}")