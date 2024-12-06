# Customization Guide

R4dar is designed to be highly extensible. This guide explains how to customize and extend its functionality.

## Extension System

Extensions in R4dar are stored in the `/extensions` directory. You can organize your extensions in subdirectories:

```
/extensions
    /my-extension
        my_custom_action.py
        my_custom_agent.py
        my_custom_handler.py
        my_custom_watcher.py
    /another-extension
        another_extension.py
```

To enable your extensions, add them to `config.yml`:

```yaml
extensions_dir: "./extensions"
active_extensions:
  - my-extension
```

## 1. Actions

Actions are commands that can be executed via the Telegram interface. They provide interactive functionality to users.

### Creating an Action

```python
# extensions/your-username/my_custom_action.py
from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.util.logging import Logger

class MyCustomAction(BaseAction):
    """Custom action implementation"""
    
    # This spec defines how the action appears in Telegram
    spec = ActionSpec(
        name="my_action",  # Command name: /my_action
        description="Performs custom analysis",  # Shows in /help
        help_text="Usage: /my_action <argument>",  # Detailed help text
        arguments=[
            ActionArgument(
                name="arg1",p
                description="First argument",
                required=True
            )
        ]
    )
    
    def __init__(self):
        self.logger = Logger("MyCustomAction")
    
    async def execute(self, arg1: str) -> str:
        """Execute the action
        
        This method is called when a user invokes the command in Telegram.
        The return value is sent as a message to the user.
        """
        try:
            result = f"Processed {arg1}"
            return result
        except Exception as e:
            self.logger.error(f"Error in action: {str(e)}")
            return "An error occurred"
```

The action will automatically appear in Telegram as `/my_action` and be included in `/help`.

## 2. Agents

Agents are AI-powered components that can process messages and perform complex tasks. They don't have a predefined interface 

### Creating an Agent

```python
# extensions/your-username/my_custom_agent.py
from src.agents.base_agent import BaseAgent
from typing import Dict, Any, List
from src.util.logging import Logger

class MyCustomAgent(BaseAgent):
    """Custom agent for specialized analysis"""
    
    def __init__(self):
        # Define the agent's specialized capabilities
        custom_prompt = """You are specialized in X.
        Your responsibilities:
        1. Task A
        2. Task B
        3. Task C"""
        
        # Specify which commands this agent can use
        command_names = [
            'semantic_search',  # For searching code semantically
            'grep_search'       # For pattern matching
        ]
        
        # Initialize with custom prompt and allowed commands
        super().__init__(custom_prompt=custom_prompt, command_names=command_names)
        self.logger = Logger("MyCustomAgent")
    
    async def process_message(self, message: str) -> str:
        """Process a message from the user
        
        This is the main entry point for agent interaction.
        """
        try:
            # Your message processing logic here
            response = await self.chat_completion([
                {"role": "user", "content": message}
            ])
            return response
        except Exception as e:
            self.logger.error(f"Error processing message: {str(e)}")
            return "An error occurred"
```

The agent will automatically have access to the specified commands from the action registry. The base agent handles:
1. Filtering available commands based on command_names
2. Building command documentation into the system prompt
3. Validating and executing commands

You don't need to implement `_get_available_commands` - just pass the command names you want to use to `super().__init__`.

## 3. Watchers

Watchers monitor external data sources and generate events when changes are detected.

### Creating a Watcher

```python
# extensions/your-username/my_custom_watcher.py
from src.watchers.base import BaseWatcher
from src.handlers.event_bus import EventBus
from src.util.logging import Logger
import asyncio

class MyCustomWatcher(BaseWatcher):
    """Custom watcher implementation"""
    
    def __init__(self):
        self.logger = Logger("MyCustomWatcher")
        self.event_bus = EventBus()
        self.running = False
    
    async def start(self):
        """Start the watcher"""
        self.running = True
        while self.running:
            try:
                # Your monitoring logic here
                changes = await self._check_for_changes()
                if changes:
                    await self._emit_event(changes)
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                self.logger.error(f"Error in watcher: {str(e)}")
                await asyncio.sleep(60)
    
    async def stop(self):
        """Stop the watcher"""
        self.running = False
    
    async def _check_for_changes(self):
        """Check for changes in data source"""
        # Your change detection logic here
        pass
    
    async def _emit_event(self, changes):
        """Emit event when changes are detected"""
        await self.event_bus.emit("custom_event", {
            "source": "my_custom_watcher",
            "changes": changes
        })
```

## 4. Event Handlers

Event handlers process events emitted by watchers and perform actions in response.

### Creating an Event Handler

```python
# extensions/your-username/my_custom_handler.py
from src.handlers.base import Handler, HandlerTrigger
from src.services.telegram import TelegramService
from src.util.logging import Logger

class MyCustomHandler(Handler):
    """Custom event handler"""
    
    def __init__(self):
        self.logger = Logger("MyCustomHandler")
        self.telegram = TelegramService.get_instance()
    
    @classmethod
    def get_triggers(cls) -> list[HandlerTrigger]:
        """Define which events this handler listens for"""
        return [HandlerTrigger.CUSTOM_EVENT]
    
    async def handle(self) -> None:
        """Handle the event"""
        try:
            # Extract event data
            payload = self.context.get("payload", {})
            
            # Process the event
            if self._is_relevant(payload):
                await self._process_event(payload)
                
        except Exception as e:
            self.logger.error(f"Error in handler: {str(e)}")
    
    def _is_relevant(self, payload: dict) -> bool:
        """Check if event is relevant"""
        return True
    
    async def _process_event(self, payload: dict) -> None:
        """Process the event"""
        # Your event processing logic here
        await self.telegram.send_message("Event processed!")
```

## Best Practices

1. **Error Handling**
   - Use try-except blocks in all async methods
   - Log errors with context
   - Fail gracefully and notify users when appropriate

2. **Performance**
   - Implement proper sleep intervals in watchers
   - Use async/await for I/O operations
   - Cache frequently used data

3. **Security**
   - Validate all input data
   - Use environment variables for sensitive data
   - Implement rate limiting for external APIs

4. **Documentation**
   - Document your extension's purpose and functionality
   - Include usage examples
   - List all configuration options