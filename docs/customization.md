# Customization Guide

R4dar is designed to be highly extensible. This guide explains how to customize and extend its functionality.
See [extensions/example](../extensions/example) for an example extension.

## Extension System

Extensions in r4dar are stored in the `/extensions` directory. Each extension is expected to be a directory containing Python files.

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
2. **Jobs** handle long-running tasks and maintain state. They can be managed by users via the bot interface.
3. **Agents** are AI-powered components that process messages and perform complex tasks.
4. **Watchers** monitor external sources for events and trigger handlers when events occur.
5. **Handlers** process events emitted by watchers.

## 1. Actions

Actions are the basic building blocks of R4dar's functionality. Actions in registered extensions automatically appear in Telegram as commands and are made available to the LLM agents.

### Creating an Action

Actions must inherit from `BaseAction` and implement the `execute` method. Create a new Python file in your extension directory:

```python
# extensions/my-extension/my_custom_action.py
from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.util.logging import Logger

class MyCustomAction(BaseAction):
    """Custom action implementation"""
    
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
                required=False,
                type=bool,  # Argument type (str, int, bool, etc.)
                default=False  # Default value for optional arguments
            )
        ]
    )
    
    def __init__(self):
        self.logger = Logger("MyCustomAction")
    
    async def execute(self, arg1: str, verbose: bool = False) -> str:
        """Execute the action
        
        This method is called when a user invokes the command in Telegram.
        The return value is sent as a message to the user.
        """
        try:
            # Your action logic here
            result = f"Processed {arg1}"
            if verbose:
                result += " with verbose output"
            return result
            
        except Exception as e:
            self.logger.error(f"Error in action: {str(e)}")
            return "An error occurred"
```

The action will be automatically discovered and registered when your extension is loaded. No additional registration code is needed.

### Action Arguments

Arguments define what parameters your action accepts. Each argument is defined using `ActionArgument`:

```python
ActionArgument(
    name="arg_name",          # Name of the argument
    description="Description", # Help text for the argument
    required=True,            # Whether the argument is required
    type=str,                 # Argument type (str, int, bool, float, etc.)
    default=None,             # Default value for optional arguments
    choices=None,             # List of valid values (optional)
    help_text=None           # Detailed help text (optional)
)
```

Arguments can be:
- Required positional arguments: `arg1`
- Optional flag arguments: `--verbose`
- Optional value arguments: `--limit 10`

The argument type determines how the input is parsed:
- `str`: Text input (default)
- `int`: Integer numbers
- `float`: Decimal numbers
- `bool`: True/False flags
- `list`: List of values (comma-separated)

### Action Results

Actions can return results in two ways:

1. Simple string return:
```python
return "Operation completed successfully"
```

2. Using `ActionResult` for more control:
```python
from src.actions.result import ActionResult

return ActionResult(
    content="Operation completed successfully",
    error=None  # Optional error message
)
```

### Built-in Actions

R4dar comes with several built-in actions:

- `help` - Display help information about available commands
- `db_query` - Query the database
- `embeddings` - Manage embeddings
- `files` - Search for files
- `semantic` - Perform semantic search
- `jobs`, `job`, `stop` - Job management commands
- `sync` - Synchronize data from external sources

You can find these in `src/actions/` for reference when building your own actions.

## 2. Agents

Agents are AI-powered components that can process messages and perform complex tasks. They inherit from `BaseAgent` and implement specific methods for autonomous task execution.

### Creating an Agent

```python
# extensions/your-username/my_custom_agent.py
from src.agents.base_agent import BaseAgent, AgentResult
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
    
    async def execute_step(self) -> AgentResult:
        """Execute a single step of the task
        
        This method should:
        1. Plan the next step based on current state
        2. Execute the planned action
        3. Update the agent's state
        4. Return an AgentResult
        """
        try:
            # Plan next step
            plan = await self.plan_next_step(self.state)
            
            # Execute planned action
            result = await self.execute_action(plan["action"], plan["input"])
            
            # Record the step
            self.record_step(
                action=plan["action"],
                input_data=plan["input"],
                output_data=result,
                reasoning=plan["reasoning"],
                next_action=plan["next_action"]
            )
            
            # Update state
            self.state["last_result"] = result
            
            return AgentResult(success=True, data=result)
            
        except Exception as e:
            self.logger.error(f"Error in step execution: {str(e)}")
            return AgentResult(success=False, error=str(e))
    
    async def plan_next_step(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """Plan the next step based on current state
        
        This method should:
        1. Analyze the current state
        2. Decide what action to take next
        3. Return a plan with action, input, reasoning, and next_action
        """
        # Example planning logic
        task = current_state["task"]
        last_result = current_state.get("last_result")
        
        # Use LLM to decide next step
        plan = await self.chat_completion([
            {"role": "system", "content": "Plan the next step based on the current state."},
            {"role": "user", "content": f"Task: {task}\nLast result: {last_result}"}
        ])
        
        return {
            "action": plan["action"],
            "input": plan["input"],
            "reasoning": plan["reasoning"],
            "next_action": plan["next_action"]
        }
    
    def is_task_complete(self) -> bool:
        """Check if the task is complete
        
        This method should analyze the current state and determine
        if the task's goal has been achieved.
        """
        # Example completion check
        return (
            self.state.get("status") == "completed" or
            self.state.get("goal_achieved") == True
        )

### Execution Logic

The BaseAgent provides a structured framework for autonomous task execution:

1. **Task Execution Flow**:
   - Each task is broken down into steps
   - Steps are executed sequentially with safety limits
   - Maximum steps and timeout constraints are enforced
   - State is tracked throughout execution

2. **Step Execution**:
   - `execute_step()`: Executes a single step of the task
   - `plan_next_step()`: Plans what action to take next
   - `is_task_complete()`: Checks if the task's goal is achieved
   - `record_step()`: Records execution history

3. **Safety and Monitoring**:
   - Maximum 10 steps per task by default
   - 5-minute timeout per task
   - Full execution history is recorded
   - State tracking for debugging

4. **Results and State**:
   - Each step returns an `AgentResult`
   - Results can indicate success, failure, or need for user input
   - Execution summary available with full step history
   - State is maintained throughout task execution

The agent will automatically have access to the specified commands from the action registry. The base agent handles:
1. Filtering available commands based on command_names
2. Building command documentation into the system prompt
3. Validating and executing commands
4. Managing execution state and history

You don't need to implement `_get_available_commands` - just pass the command names you want to use to `super().__init__`.

## 3. Handlers

Handlers process events triggered by watchers and other components. They allow you to react to changes in projects, assets, and other system events.

### Creating a Handler

Handlers must inherit from `Handler` and implement the `handle` method. Create a new Python file in your extension directory:

```python
# extensions/my-extension/my_custom_handler.py
from src.handlers.base import Handler, HandlerTrigger, HandlerResult
from src.util.logging import Logger
from typing import List

class MyCustomHandler(Handler):
    """Custom handler for project events"""
    
    def __init__(self):
        super().__init__()
        self.logger = Logger("MyCustomHandler")
    
    @classmethod
    def get_triggers(cls) -> List[HandlerTrigger]:
        """Define which events this handler responds to"""
        return [
            HandlerTrigger.PROJECT_UPDATE,
            HandlerTrigger.NEW_PROJECT
        ]
    
    async def handle(self) -> HandlerResult:
        """Handle the event
        
        The event context is available in self.context
        Returns a HandlerResult indicating success/failure and any relevant data
        """
        try:
            # Get event data from context
            project = self.context.get('project')
            if not project:
                return HandlerResult(success=False, data={"error": "No project in context"})
                
            if self.trigger == HandlerTrigger.PROJECT_UPDATE:
                old_project = self.context.get('old_project')
                result = await self._handle_project_update(project, old_project)
            elif self.trigger == HandlerTrigger.NEW_PROJECT:
                result = await self._handle_new_project(project)
                
            return HandlerResult(success=True, data=result)
                
        except Exception as e:
            self.logger.error(f"Error in handler: {str(e)}")
            return HandlerResult(success=False, data={"error": str(e)})
    
    async def _handle_project_update(self, project, old_project) -> dict:
        """Handle project update event"""
        # Your update logic here
        return {"status": "updated", "project_id": project.id}
        
    async def _handle_new_project(self, project) -> dict:
        """Handle new project event"""
        # Your new project logic here
        return {"status": "created", "project_id": project.id}

### Handler Results

Handlers must return a `HandlerResult` object that indicates the success or failure of the operation and includes any relevant data:

```python
from src.handlers.base import HandlerResult

# Successful result with data
return HandlerResult(success=True, data={"status": "completed", "items_processed": 5})

# Failed result with error information
return HandlerResult(success=False, data={"error": "Failed to process project"})
```

The `HandlerResult` is used by the event bus to:
1. Track handler execution success/failure
2. Log handler results in the event log
3. Provide feedback to other system components

### Available Triggers

The following event triggers are available:

- `HandlerTrigger.NEW_PROJECT` - Triggered when a new project is added
- `HandlerTrigger.PROJECT_UPDATE` - Triggered when a project is updated
- `HandlerTrigger.PROJECT_REMOVE` - Triggered when a project is removed
- `HandlerTrigger.NEW_ASSET` - Triggered when a new asset is added
- `HandlerTrigger.ASSET_UPDATE` - Triggered when an asset is updated
- `HandlerTrigger.ASSET_REMOVE` - Triggered when an asset is removed
- `HandlerTrigger.GITHUB_PUSH` - Triggered when a GitHub push event is received
- `HandlerTrigger.GITHUB_PR` - Triggered when a GitHub pull request event is received
- `HandlerTrigger.BLOCKCHAIN_EVENT` - Triggered when a blockchain event is detected

### Handler Context

The context passed to handlers contains relevant data for the event:

- For project events:
  - `project`: The Project instance
  - `old_project`: The previous state (for updates)
  - `removed`: Boolean flag (for removals)
  
- For asset events:
  - `asset`: The Asset instance
  - `old_revision`: Previous revision (for updates)
  - `new_revision`: New revision (for updates)
  - `old_path`: Path to old version (for file updates)
  - `new_path`: Path to new version (for file updates)

### Custom Triggers

In addition to the built-in triggers, you can define custom triggers for your handlers:

```python
from src.handlers.base import Handler, HandlerTrigger

# Register a custom trigger
MY_CUSTOM_TRIGGER = HandlerTrigger.register_custom_trigger("MY_CUSTOM_TRIGGER")

class MyCustomHandler(Handler):
    """Handler for custom events"""
    
    @classmethod
    def get_triggers(cls) -> List[HandlerTrigger]:
        return [MY_CUSTOM_TRIGGER]
    
    async def handle(self) -> None:
        # Handle the custom event
        pass

# Emit the custom trigger from your code
await handler_registry.trigger_event(MY_CUSTOM_TRIGGER, {
    "data": "Custom event data"
})
```

Built-in triggers include:
- `HandlerTrigger.NEW_PROJECT` - New project added
- `HandlerTrigger.PROJECT_UPDATE` - Project updated
- `HandlerTrigger.PROJECT_REMOVE` - Project removed
- `HandlerTrigger.NEW_ASSET` - New asset added
- `HandlerTrigger.ASSET_UPDATE` - Asset updated
- `HandlerTrigger.ASSET_REMOVE` - Asset removed
- `HandlerTrigger.GITHUB_PUSH` - GitHub push event
- `HandlerTrigger.GITHUB_PR` - GitHub pull request event
- `HandlerTrigger.BLOCKCHAIN_EVENT` - Blockchain event

## 4. Watchers

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