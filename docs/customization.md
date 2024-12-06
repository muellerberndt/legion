# Customization Guide

R4dar is designed to be highly extensible. This guide explains how to customize and extend its functionality.
See [extensions/example](../extensions/example) for an example extension.

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

## Core concepts

1. **Actions** are the basic building blocks of R4dar's functionality. Each action represents a specific command that can be invoked via Telegram or used by agents.
2. **Jobs** handle long-running tasks and maintain state. The can be managed by users via the bot interface.
3. **Agents** are AI-powered components that process messages and perform complex tasks.
4. **Watchers** monitor external sources for events and trigger handlers when events occur.
5. **Handlers** process events emitted by watchers.

## 1. Actions

Actions are the building blocks of R4dar's functionality. Each action represents a specific command that can be invoked via Telegram or used by agents.

### Action Specification

Before creating an action, you need to define its specification using `ActionSpec`. This tells R4dar:
- How the action appears in Telegram
- What parameters it accepts
- When agents should use it
- How to display help text

```python
from src.actions.base import ActionSpec, ActionArgument

# Define the action's specification
spec = ActionSpec(
    name="my_action",          # Command name: /my_action
    description="Performs custom analysis",  # Short description for /help
    help_text="""Detailed help text explaining usage.
    
Usage:
/my_action <argument>

This command performs custom analysis on the provided argument.
Results are returned as formatted text.

Examples:
/my_action example
/my_action --verbose example""",  # Shown with /help my_action
    agent_hint="Use this command when you need to perform custom analysis on user input",  # Helps agents decide when to use this command
    arguments=[
        ActionArgument(
            name="arg1",
            description="First argument",
            required=True
        ),
        ActionArgument(
            name="verbose",
            description="Enable verbose output",
            required=False
        )
    ]
)
```

### Creating an Action

Actions must inherit from `BaseAction` and implement the `execute` method:

```python
from src.actions.base import BaseAction
from src.jobs.manager import JobManager
from src.util.logging import Logger

class MyCustomAction(BaseAction):
    """Custom action implementation"""
    
    # Use the spec we defined above
    spec = spec
    
    def __init__(self):
        self.logger = Logger("MyCustomAction")
    
    async def execute(self, arg1: str, verbose: bool = False) -> str:
        """Execute the action
        
        This method is called when a user invokes the command in Telegram.
        The return value is sent as a message to the user.
        """
        try:
            # Create and submit a job
            job = MyCustomJob(arg1, verbose=verbose)
            job_manager = JobManager()
            job_id = await job_manager.submit_job(job)
            
            return f"Started analysis (Job ID: {job_id})"
            
        except Exception as e:
            self.logger.error(f"Error in action: {str(e)}")
            return "An error occurred"
```

### Creating Jobs

Since actions are blocking, your action should launch a job if it needs to perform long-running tasks. Users can manage jobs using:

The job system provides:
- State management (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`)
- Result storage via `JobResult`
- Automatic persistence to database
- Job cancellation support
- Progress tracking
- Output collection

Jobs inherit from the `Job` class:

```python
from src.jobs.base import Job, JobType, JobResult, JobStatus
from typing import Optional

class MyCustomJob(Job):
    """Job for handling custom analysis"""
    
    def __init__(self, target: str, verbose: bool = False):
        super().__init__(JobType.ANALYSIS)  # Set appropriate job type
        self.target = target
        self.verbose = verbose
        self.result: Optional[JobResult] = None
    
    async def start(self) -> None:
        """Start the job - this is called by the job manager"""
        try:
            self.status = JobStatus.RUNNING
            
            # Perform the actual work
            analysis_result = await self._analyze(self.target)
            
            # Store results
            self.result = JobResult(
                success=True,
                message="Analysis completed successfully",
                data=analysis_result  # Store structured data
            )
            if self.verbose:
                self.result.add_output("Detailed analysis log...")
                
            self.status = JobStatus.COMPLETED
            
        except Exception as e:
            self.status = JobStatus.FAILED
            self.result = JobResult(
                success=False,
                message=f"Analysis failed: {str(e)}"
            )
            raise
            
    async def stop(self) -> None:
        """Stop the job - called when user cancels"""
        self.status = JobStatus.CANCELLED
        
    async def _analyze(self, target: str) -> dict:
        """Internal method to perform analysis"""
        # Your analysis logic here
        return {"result": "analysis output"}
```

`JobResult` can store:
- Success/failure status
- User-friendly message
- Structured data (as JSON)
- Multiple text outputs (for logging/progress

Users can check job status and results using:
- `/job <job_id>` - Get current status and results
- `/jobs` - List recent jobs
- `/stop <job_id>` - Cancel a running job

### Launching Jobs from Actions

Jobs can be launched from actions using the `JobManager`. Here's how:

```python
from src.jobs.manager import JobManager

class MyAction(BaseAction):
    async def execute(self, *args, **kwargs) -> str:
        try:
            # Create job instance
            job = MyCustomJob(*args, **kwargs)
            
            # Get job manager instance
            job_manager = JobManager()
            
            # Submit job and get ID
            job_id = await job_manager.submit_job(job)
            
            # Return job ID to user
            return f"Started job with ID: {job_id}"
            
        except Exception as e:
            self.logger.error(f"Failed to start job: {str(e)}")
            return f"Error starting job: {str(e)}"
```

The job manager handles:
- Job persistence to database
- State management
- Concurrent execution
- Error handling
- Result storage

The action will automatically appear in Telegram as `/my_action` and be included in `/help`.

## 2. Agents

Agents are AI-powered components that can process messages and perform complex tasks. They don't have a predefined interface - just inherit from `BaseAgent` and specify the actions the agent can use in the constructor.

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

Watchers monitor external sources for events. To activate a watcher:

1. Enable watchers in `config.yml`:
```yaml
watchers:
  enabled: true  # Master switch for all watchers
  webhook_port: 8080  # Port for webhook server
  active_watchers:  # List of watchers to enable
    - github       # Monitor GitHub repositories
    - quicknode    # Monitor blockchain events
    - immunefi     # Monitor bounty program updates
```

2. Configure watcher-specific settings:
```yaml
github:
  api_token: "your-github-token"  # For GitHub watcher
  poll_interval: 300  # Check every 5 minutes

quicknode:
  endpoints:
    - name: "mainnet"
      url: "your-quicknode-endpoint"
      chain_id: 1
```

3. Start the server with watchers enabled:
```bash
./r4dar.sh server start
```

The server will:
- Load all enabled watchers
- Start the webhook server if needed
- Begin monitoring configured sources

Available watchers:
- `github`: Monitors repositories for changes
- `quicknode`: Monitors blockchain events
- `immunefi`: Monitors bounty program updates

Each watcher can trigger handlers when events occur. See the Handlers section for details on processing these events.

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

Event handlers process events emitted by watchers and perform actions in response. They inherit from `Handler` and implement the `handle` method. Each handler must subscribe to specific event types via the `get_triggers` method.

### Built-in Handler Triggers

The framework provides several built-in triggers that handlers can listen for:

- `NEW_PROJECT`: When a new project is added
- `PROJECT_UPDATE`: When a project is updated
- `PROJECT_REMOVE`: When a project is removed
- `NEW_ASSET`: When a new asset is added
- `ASSET_UPDATE`: When an asset is updated
- `ASSET_REMOVE`: When an asset is removed
- `GITHUB_PUSH`: When a GitHub push event is received
- `GITHUB_PR`: When a GitHub pull request event is received
- `BLOCKCHAIN_EVENT`: When a blockchain event is detected

### Custom Handler Triggers

You can define custom triggers for your extensions without modifying the base framework. Here's how:

1. Register your custom trigger:
```python
from src.handlers.base import HandlerTrigger

# Register a custom trigger
MY_CUSTOM_TRIGGER = HandlerTrigger.register_custom_trigger("MY_CUSTOM_TRIGGER")
```

2. Use the custom trigger in your handler:
```python
class MyCustomHandler(Handler):
    @classmethod
    def get_triggers(cls) -> list[HandlerTrigger]:
        return [MY_CUSTOM_TRIGGER]
    
    async def handle(self) -> None:
        # Handle the custom event
        pass
```

3. Emit the custom trigger from your watcher or other components:
```python
from src.handlers.event_bus import EventBus

event_bus = EventBus()
await event_bus.trigger_event(MY_CUSTOM_TRIGGER, {
    "source": "my_custom_watcher",
    "data": my_event_data
})
```

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

### Custom event types

If you need to define custom event types, you can do so by creating a new class that inherits from `HandlerTrigger` and registering it in `Handler.get_triggers`.

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