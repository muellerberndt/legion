import asyncio
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from src.interfaces.base import Interface
from src.actions.registry import ActionRegistry
from src.util.logging import Logger
from src.config.config import Config
from src.services.telegram import TelegramService
from src.ai.chatbot import Chatbot
import telegram
from src.util.command_parser import CommandParser
from src.actions.result import ActionResult, ResultType
import json
from typing import Any, Dict, List, Optional
import tempfile
import re


class TelegramInterface(Interface):
    """Telegram bot interface"""

    MAX_MESSAGE_LENGTH = 4096  # Telegram's message length limit

    def __init__(self, action_registry: ActionRegistry):
        super().__init__()
        self.logger = Logger("TelegramInterface")
        self.action_registry = action_registry
        self.app = None
        self.service = TelegramService.get_instance()
        self._agents = {}  # Chat ID -> TelegramAutobot
        self._polling_task = None
        self._initialized = False
        self.command_parser = CommandParser()

    def _format_result(self, result: ActionResult) -> str:
        """Format an ActionResult for Telegram output"""
        # Handle error results first
        if result.type == ResultType.ERROR:
            return f"Error: {result.error or result.content}"

        # Handle empty results
        if result.content is None:
            return "No results available."

        # Handle job results
        if result.type == ResultType.JOB:
            # Format job launch message with command on new line
            return f"Started job {result.job_id}\n\nUse /job {result.job_id} to check status"

        # Dispatch to appropriate formatter based on type
        formatters = {
            ResultType.TEXT: self._format_text_result,
            ResultType.LIST: self._format_list_result,
            ResultType.TREE: self._format_tree_result,
            ResultType.JSON: self._format_json_result,
        }

        formatter = formatters.get(result.type, str)
        formatted = formatter(result)

        return formatted

    def _format_text_result(self, result: ActionResult) -> str:
        """Format a text result"""
        return str(result.content)

    def _format_list_result(self, result: ActionResult) -> str:
        """Format a list result"""
        items = result.content
        if not items:
            return "No items found."

        # Get total count from metadata if available
        total = result.metadata.get("total", len(items)) if result.metadata else len(items)
        lines = [f"📋 Found {total} items:"]

        # Add truncation note if needed
        if result.metadata and "truncated" in result.metadata:
            lines.append(f"(Showing first {len(items)} of {total} items)\n")

        # Format each item
        for i, item in enumerate(items, 1):
            lines.append(f"{i}. {str(item)}")

        return "\n".join(lines)

    def _format_tree_result(self, result: ActionResult) -> str:
        """Format a tree result"""
        return "\n".join(self._format_tree_data(result.content))

    def _format_tree_data(self, data: Dict[str, Any], level: int = 0) -> List[str]:
        """Format tree data recursively"""
        lines = []
        indent = "  " * level
        for key, value in data.items():
            formatted_value = self._format_tree_value(key, value, level)
            if formatted_value is not None:
                lines.extend(formatted_value)
            else:
                lines.append(f"{indent}{key}: {str(value)}")
        return lines

    def _format_tree_value(self, key: str, value: Any, level: int) -> Optional[List[str]]:
        """Format a single value in the tree"""
        indent = "  " * level
        if hasattr(value, "value"):
            return [f"{indent}{key}: {self._format_status_value(key, value.value)}"]
        elif isinstance(value, dict):
            return [f"{indent}{key}:"] + self._format_tree_data(value, level + 1)
        elif isinstance(value, list):
            return self._format_tree_list(key, value, level)
        return None

    def _format_status_value(self, key: str, value: str) -> str:
        """Format a status value with emoji"""
        if key == "Status":
            status_emojis = {
                "running": "🏃 Running",
                "completed": "✅ Completed",
                "failed": "❌ Failed",
                "cancelled": "⛔️ Cancelled",
                "pending": "⏳ Pending",
            }
            return status_emojis.get(value, value)
        return value

    def _format_tree_list(self, key: str, items: List[Any], level: int) -> List[str]:
        """Format a list in the tree"""
        lines = [f"{'  ' * level}{key}:"]
        for item in items:
            if isinstance(item, dict):
                lines.extend(self._format_tree_data(item, level + 1))
            else:
                lines.append(f"{'  ' * (level + 1)}• {str(item)}")
        return lines

    def _format_json_result(self, result: ActionResult) -> str:
        """Format a JSON result"""
        formatted_json = json.dumps(result.content, indent=2)
        return f"```json\n{formatted_json}\n```"

    def _create_command_handler(self, command_name: str, action_handler):
        """Create a command handler function for a specific command"""

        async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            try:
                # Get command spec
                action = self.action_registry.get_action(command_name)
                if not action:
                    raise ValueError(f"Action not found for command: {command_name}")
                _, spec = action

                # Parse command and arguments
                _, args_str = self.command_parser.parse_command(update.message.text)
                args = self.command_parser.parse_arguments(args_str, spec)

                # Validate arguments
                self.command_parser.validate_arguments(args, spec)

                # Create update callback
                chat_id = str(update.message.chat_id)

                async def update_callback(message: str):
                    await self._send_update(chat_id, message)

                # Send initial status
                await self._send_update(chat_id, f"🏃 Starting command: /{command_name}")

                # Execute the action with the arguments and update callback
                if isinstance(args, dict):
                    args["_update_callback"] = update_callback
                    result = await action_handler(**args)
                else:
                    result = await action_handler(*args, _update_callback=update_callback)

                if result:
                    # Handle the result
                    formatted_result = await self._handle_command_result(result)

                    # Use TelegramService to handle message sending with proper size handling
                    service = TelegramService.get_instance()
                    service.chat_id = str(update.message.chat_id)
                    await service.send_message(formatted_result)

            except Exception as e:
                self.logger.error(f"Error executing command {command_name}: {e}")
                error_msg = f"Error executing command: {str(e)}"
                service = TelegramService.get_instance()
                service.chat_id = str(update.message.chat_id)
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

        # Register message handler for all messages
        self.app.add_handler(MessageHandler(filters.TEXT, self._handle_message))

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
        if not update.message or not update.message.text:
            return

        text = update.message.text
        chat_id = str(update.message.chat_id)

        try:
            # Check if it's a direct command
            if text.startswith("/"):
                command, args_str = self.command_parser.parse_command(text)
                if command == "start":
                    await self._handle_start_command(update, context)
                    return

                if command in self.action_registry.get_actions():
                    # Execute command directly through action registry
                    action = self.action_registry.get_action(command)
                    if not action:
                        raise ValueError(f"Action not found for command: {command}")
                    handler, spec = action

                    # Parse and validate arguments
                    args = self.command_parser.parse_arguments(args_str, spec)
                    self.command_parser.validate_arguments(args, spec)

                    # Create update callback
                    async def update_callback(message: str):
                        if message and message.strip():
                            await self._send_update(chat_id, message)

                    # Execute the command
                    if isinstance(args, dict):
                        args["_update_callback"] = update_callback
                        result = await handler(**args)
                    else:
                        result = await handler(*args, _update_callback=update_callback)

                    # Only send result if it's not None and not empty
                    if result:
                        formatted_result = await self._handle_command_result(result)
                        if formatted_result and formatted_result.strip():
                            await self.send_message(formatted_result, chat_id)
                    return

            # For non-command messages or unknown commands, use the Chatbot
            await self.handle_message(text, chat_id)

        except Exception as e:
            self.logger.error(f"Error in message handler: {e}")
            error_msg = str(e)
            # Remove any special characters that could cause Telegram parsing issues
            error_msg = error_msg.replace("`", "").replace("*", "").replace("_", "")
            await self.send_message(f"Error: {error_msg}", chat_id)

    async def handle_message(self, content: str, session_id: str) -> None:
        """Handle a non-command message through the conversation agent"""
        try:
            # Get or create conversation agent for this session
            if session_id not in self._agents:
                self._agents[session_id] = Chatbot()

            agent = self._agents[session_id]

            # Create update callback
            async def update_callback(message: str):
                await self.send_message(message, session_id)

            # Process message with update callback
            response = await agent.process_message(content, update_callback=update_callback)
            await self.send_message(response, session_id)

        except Exception as e:
            self.logger.error(f"Error in conversation: {e}")
            await self.send_message(f"Sorry, I encountered an error: {str(e)}", session_id)

    async def send_message(self, content: str, session_id: str) -> None:
        """Send a message to a specific chat, handling long content appropriately"""
        if not self.app or not self.app.bot:
            self.logger.error("Bot not initialized")
            return

        try:
            # Truncate content if needed
            truncated, full_content = self._truncate_content(content)

            # Send truncated message
            await self.app.bot.send_message(chat_id=session_id, text=truncated)

            # If content was truncated, send full version as HTML
            if full_content:
                html_content = self._format_as_html(full_content)

                with tempfile.NamedTemporaryFile(mode="w", suffix=".html", encoding="utf-8") as f:
                    f.write(html_content)
                    f.flush()

                    # Send the HTML file
                    await self.app.bot.send_document(
                        chat_id=session_id, document=open(f.name, "rb"), caption="Full response (formatted as HTML)"
                    )

        except Exception as e:
            self.logger.error(f"Failed to send message: {e}")
            # Try to send error message
            try:
                error_msg = f"Error sending message: {str(e)}"
                await self.app.bot.send_message(chat_id=session_id, text=error_msg)
            except Exception:
                self.logger.error("Failed to send error message")

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

    async def _handle_command_result(self, result: Any) -> str:
        """Handle and format command results"""
        try:
            # If result is already an ActionResult, format it
            if isinstance(result, ActionResult):
                # Special handling for job tree results
                if result.type == ResultType.TREE and isinstance(result.content, dict) and "id" in result.content:
                    # Format job info with emojis and nice labels
                    job_info = {
                        "🔍 Job": result.content["id"],
                        "Type": result.content["type"],
                    }

                    # Format status with emoji
                    status = result.content["status"]
                    status_value = status.value if hasattr(status, "value") else str(status)
                    if status_value == "running":
                        job_info["Status"] = "🏃 Running"
                    elif status_value == "completed":
                        job_info["Status"] = "✅ Completed"
                    elif status_value == "failed":
                        job_info["Status"] = "❌ Failed"
                    elif status_value == "cancelled":
                        job_info["Status"] = "⛔️ Cancelled"
                    elif status_value == "pending":
                        job_info["Status"] = "⏳ Pending"
                    else:
                        job_info["Status"] = status_value

                    # Format timestamps
                    job_info["Started"] = result.content["started_at"] or "Not started"
                    job_info["Completed"] = result.content["completed_at"] or "Not completed"

                    # Add result info if available
                    if result.content.get("success") is not None:
                        if result.content["success"]:
                            if result.content.get("message"):
                                job_info["📝 Result"] = result.content["message"]
                        elif result.content.get("error"):
                            job_info["❌ Error"] = result.content["error"]

                    # Add outputs and data if available
                    if result.content.get("outputs"):
                        job_info["Outputs"] = result.content["outputs"]
                    if result.content.get("data"):
                        job_info["Data"] = result.content["data"]

                    return self._format_result(ActionResult.tree(job_info))

                return self._format_result(result)

            # Convert other types to appropriate ActionResult and format them
            if isinstance(result, str):
                return self._format_result(ActionResult.text(result))
            elif isinstance(result, dict):
                return self._format_result(ActionResult.json(result))
            elif isinstance(result, list):
                return self._format_result(ActionResult.list(result))
            elif result is None:
                return self._format_result(ActionResult.text("Command completed successfully."))
            else:
                return self._format_result(ActionResult.text(str(result)))
        except Exception as e:
            self.logger.error(f"Error handling command result: {e}")
            return self._format_result(ActionResult.error(f"Error formatting result: {str(e)}"))

    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text messages"""
        if not update.message or not update.message.text:
            return

        chat_id = str(update.message.chat_id)
        text = update.message.text

        try:
            # Check if it's a command
            if text.startswith("/"):
                command, args_str = self.command_parser.parse_command(text)
                result = await self._handle_command(command, args_str, chat_id)
                if result:
                    await self.send_message(str(result), chat_id)
            else:
                # For non-command messages, use the agent
                agent = self._get_or_create_agent(chat_id)
                await agent.process_message(text, update_callback=lambda msg: self.send_message(msg, chat_id))
        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            self.logger.error(error_msg)
            await self.send_message(error_msg, chat_id)

    async def _handle_command(self, command: str, args_str: str, chat_id: str) -> Any:
        """Handle a command message"""
        try:
            # Get the action from registry
            action = self.action_registry.get_action(command)
            if not action:
                raise ValueError(f"Unknown command: {command}")

            handler, spec = action

            # Parse and validate arguments
            args = self.command_parser.parse_arguments(args_str, spec)
            self.command_parser.validate_arguments(args, spec)

            # Execute the command
            if isinstance(args, dict):
                result = await handler(**args)
            else:
                result = await handler(*args)

            return result

        except Exception as e:
            self.logger.error(f"Error executing command: {str(e)}")
            raise

    async def _send_update(self, chat_id: str, message: str) -> None:
        """Send a status update to a specific chat"""
        await self.send_message(message, chat_id)

    def _format_as_html(self, content: str) -> str:
        """Format content as HTML with nice styling"""
        html = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                pre { background: #f5f5f5; padding: 10px; border-radius: 5px; }
                table { border-collapse: collapse; width: 100%; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f5f5f5; }
                .tree-view { font-family: monospace; }
                .tree-view .node { margin-left: 20px; }
                .json { color: #333; }
                .json .key { color: #0066cc; }
                .json .string { color: #008800; }
                .json .number { color: #aa0000; }
                .json .boolean { color: #aa0000; }
            </style>
        </head>
        <body>
        """

        # Try to detect and format different types of content
        if content.strip().startswith(("{", "[")):
            try:
                # Format JSON with syntax highlighting
                data = json.loads(content)
                formatted = json.dumps(data, indent=2)
                html += "<pre class='json'>"
                # Add basic syntax highlighting
                formatted = formatted.replace('"', "&quot;")
                formatted = re.sub(r'(".*?"):', r'<span class="key">\1</span>:', formatted)
                formatted = re.sub(r': "(.+?)"', r': <span class="string">&quot;\1&quot;</span>', formatted)
                formatted = re.sub(r": (\d+)", r': <span class="number">\1</span>', formatted)
                formatted = re.sub(r": (true|false)", r': <span class="boolean">\1</span>', formatted)
                html += formatted
                html += "</pre>"
            except json.JSONDecodeError:
                html += f"<pre>{content}</pre>"
        elif "\n" in content and "|" in content:
            # Looks like a table, convert to HTML table
            rows = [row.strip().split("|") for row in content.strip().split("\n")]
            html += "<table>"
            for i, row in enumerate(rows):
                html += "<tr>"
                tag = "th" if i == 0 else "td"
                for cell in row:
                    html += f"<{tag}>{cell.strip()}</{tag}>"
                html += "</tr>"
            html += "</table>"
        elif content.startswith(("├", "└", "│")):
            # Looks like a tree structure
            html += "<pre class='tree-view'>"
            html += content
            html += "</pre>"
        else:
            # Default to pre-formatted text
            html += f"<pre>{content}</pre>"

        html += "</body></html>"
        return html

    def _truncate_content(self, content: str) -> tuple[str, str | None]:
        """Truncate content and return both truncated version and full content if needed"""
        if len(content) <= self.MAX_MESSAGE_LENGTH:
            return content, None

        # For JSON content, try to truncate intelligently
        if content.strip().startswith(("{", "[")):
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    if "results" in data and isinstance(data["results"], list):
                        original_count = len(data["results"])
                        data["results"] = data["results"][:10]
                        data["note"] = f"Results truncated (showing 10 of {original_count})"
                        truncated = json.dumps(data, indent=2)
                        if len(truncated) <= self.MAX_MESSAGE_LENGTH:
                            return truncated, content
            except json.JSONDecodeError:
                pass

        # For list-like content (multiple lines starting with numbers or bullets)
        if "\n" in content and any(line.strip().startswith(("- ", "* ", "1.", "2.")) for line in content.splitlines()):
            lines = content.splitlines()
            truncated_lines = []
            total_lines = len(lines)

            for line in lines[:10]:  # Keep first 10 items
                truncated_lines.append(line)

            truncated = "\n".join(truncated_lines)
            truncated += f"\n\n... (truncated, showing 10 of {total_lines} items)"

            if len(truncated) <= self.MAX_MESSAGE_LENGTH:
                return truncated, content

        # Default truncation
        truncated = content[: self.MAX_MESSAGE_LENGTH - 100] + "...\n(truncated, see full content in the HTML file)"
        return truncated, content
