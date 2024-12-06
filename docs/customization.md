# Customization Guide

R4dar is designed to be highly extensible. This guide explains how to customize and extend its functionality.

There are four types of extensions:

1. **Actions** are basic operations that can be executed by the user and LLM agents. Actions should return immediately but may launch longer-running jobs.
2. **Agents** use actions to perform tasks on behalf of the user.
3. **Watchers** monitor external sources for new data, run repeating actions, and trigger events.
4. **Event handlers** react to specific types of events (blockchain events, GitHub events, etc.).

## Custom Event Handlers

Event handlers react to specific types of events (blockchain events, GitHub events, etc.) and perform custom actions. To add a new handler, tou need to create a handler class and register for a [trigger event]().



### Creating a Handler

1. Create a new file in the `extensions` directory:

```python
# extensions/my_custom_handler.py
from r4dar.handlers import Handler
from r4dar.triggers import BlockchainEvent
from r4dar.services import TelegramService
from r4dar.util.logging import Logger

class MyCustomHandler(Handler):
    """Custom handler for monitoring specific events"""
    
    def __init__(self):
        super().__init__()
        self.logger = Logger("MyCustomHandler")
        self.telegram = TelegramService.get_instance()
        
    @classmethod
    def get_triggers(cls) -> list:
        """Define which events this handler listens for"""
        return [BlockchainEvent]
        
    async def handle(self) -> None:
        """Process the event"""
        try:
            # Extract event data
            payload = self.context.get("payload", {})
            
            # Your custom logic here
            # Example: Monitor specific contract events
            if self._is_relevant_event(payload):
                await self._process_event(payload)
                
        except Exception as e:
            self.logger.error(f"Error in handler: {str(e)}")
            
    def _is_relevant_event(self, payload: dict) -> bool:
        """Check if event is relevant for this handler"""
        # Your filtering logic here
        return True
        
    async def _process_event(self, payload: dict) -> None:
        """Process relevant event"""
        # Your processing logic here
        await self.telegram.send_message("Event detected!")
```

2. Register your handler in `extensions/__init__.py`:

```python
from .my_custom_handler import MyCustomHandler

__all__ = ['MyCustomHandler']
```

## Custom Analysis Agents

Analysis agents perform specialized analysis tasks using AI or other methods.

### Creating an Agent

```python
# extensions/my_custom_agent.py
from r4dar.agents import BaseAgent
from typing import Dict, Any

class MyCustomAgent(BaseAgent):
    """Custom agent for specialized analysis"""
    
    def __init__(self):
        # Add specialized prompt for your analysis
        custom_prompt = """You are specialized in analyzing X.
        Your task is to:
        1. Analyze A
        2. Detect B
        3. Report C"""
        
        super().__init__(custom_prompt=custom_prompt)
        
    async def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform custom analysis"""
        prompt = self._create_analysis_prompt(data)
        
        # Get analysis from AI
        response = await self.chat_completion([
            {"role": "user", "content": prompt}
        ])
        
        # Process and return results
        return self._process_response(response)
        
    def _create_analysis_prompt(self, data: Dict[str, Any]) -> str:
        """Create analysis prompt"""
        return f"Please analyze this data: {data}"
        
    def _process_response(self, response: str) -> Dict[str, Any]:
        """Process AI response"""
        # Your processing logic here
        return {
            "result": response,
            "confidence": 0.9
        }
```

## Custom Commands

You can add custom commands to interact with your handlers and agents via Telegram.

### Adding Commands

1. Create a command handler:

```python
# extensions/my_custom_command.py
from r4dar.actions import BaseAction, ActionSpec, ActionArgument

class MyCustomCommand(BaseAction):
    """Custom command implementation"""
    
    spec = ActionSpec(
        name="my_command",
        description="Performs custom analysis",
        help_text="Usage: /my_command <argument>",
        arguments=[
            ActionArgument(
                name="arg1",
                description="First argument",
                required=True
            )
        ]
    )
    
    async def execute(self, arg1: str) -> str:
        """Execute the command"""
        # Your command logic here
        return f"Processed {arg1}"
```

2. Register the command in `extensions/__init__.py`:

```python
from .my_custom_command import MyCustomCommand

__all__ = ['MyCustomCommand']
```

## Configuration

### Custom Settings

Add your custom settings to `config.yml`:

```yaml
custom_settings:
  my_handler:
    enabled: true
    threshold: 0.8
    target_contracts:
      - "0x123..."
      - "0x456..."
```

### Accessing Settings

```python
from r4dar.config import Config

config = Config()
settings = config.get("custom_settings.my_handler", {})
threshold = settings.get("threshold", 0.5)
```

## Testing

### Writing Tests

```python
# tests/extensions/test_my_handler.py
import pytest
from extensions.my_custom_handler import MyCustomHandler

@pytest.mark.asyncio
async def test_handler():
    handler = MyCustomHandler()
    handler.context = {"payload": {...}}
    await handler.handle()
    # Add assertions
```

### Running Tests

```bash
pytest tests/extensions/test_my_handler.py -v
```

## Best Practices

1. **Error Handling**
   - Always use try-except blocks in handlers
   - Log errors with appropriate context
   - Fail gracefully when possible

2. **Performance**
   - Cache frequently used data
   - Use async/await for I/O operations
   - Implement timeouts for external calls

3. **Security**
   - Validate all input data
   - Use environment variables for sensitive data
   - Implement rate limiting where appropriate

4. **Documentation**
   - Document your code with docstrings
   - Include usage examples
   - Explain configuration options 