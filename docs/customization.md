# Customization Guide

This guide explains how to customize and extend its functionality. See [extensions/example](../extensions/examples) for an example extension.

## Extension System

Extensions in r4dar are stored in the `/extensions` directory. Each extension is expected to be a directory containing Python files.

```
/extensions
    /my-extension
        my_custom_action.py
        my_custom_agent.py
        my_custom_handler.py
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
4. **Handlers** process events such as webhooks, scope updates, GitHub events, etc.
5. **Scheduled Actions** are actions that run automatically at configured intervals.

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

### Scheduling Actions

Actions can be configured to run automatically at specified intervals using the scheduler system. Add scheduled actions to your `config.yml`:

```yaml
scheduled_actions:
  daily_sync:
    command: sync  # The action to run
    interval_minutes: 1440  # Run daily (24 hours * 60 minutes)
    enabled: true  # Whether this scheduled action is active
  hourly_embeddings:
    command: embeddings update
    interval_minutes: 60  # Run hourly
    enabled: true
```

You can manage scheduled actions using the `/scheduler` command:
- `/scheduler list` - List all scheduled actions and their status
- `/scheduler enable <action_name>` - Enable a scheduled action
- `/scheduler disable <action_name>` - Disable a scheduled action
- `/scheduler status <action_name>` - Get detailed status of a scheduled action

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
- `scheduler` - Manage scheduled actions
- `status` - Show system status

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

## 2. Jobs

Jobs handle long-running tasks and maintain state. Each job must inherit from the `Job` base class and implement the required abstract methods.

### Creating a Job

```python
from src.jobs.base import Job, JobStatus, JobResult
from src.util.logging import Logger

class MyCustomJob(Job):
    """Custom job implementation"""
    
    def __init__(self, job_id: str, config: dict = None):
        super().__init__(job_id, config)
        self.logger = Logger("MyCustomJob")
    
    async def start(self) -> None:
        """Start the job.
        
        Required abstract method that must be implemented.
        This method should:
        1. Initialize any required resources
        2. Start the main job processing
        3. Update job status and store results
        
        The job should handle its own state management by calling:
        - self.complete(JobResult(...)) for successful completion
        - self.fail(error_message) for failures
        """
        try:
            # Your job logic here
            result = await self.process_job()
            
            # Store results on success
            self.complete(JobResult(
                success=True,
                message="Job completed successfully",
                data=result
            ))
            
        except Exception as e:
            self.logger.error(f"Error in job: {str(e)}")
            self.fail(str(e))
    
    async def stop_handler(self) -> None:
        """Handle cleanup when stopping the job.
        
        Required abstract method that must be implemented.
        This method should handle any job-specific cleanup operations such as:
        - Stopping external processes (e.g., kill child processes)
        - Cleaning up temporary files
        - Closing network connections
        - Releasing resources
        - Saving partial results if applicable
        
        The base Job class will handle marking the job as cancelled after this handler completes.
        Raise an exception if cleanup fails.
        """
        try:
            # Your cleanup logic here
            await self.cleanup_resources()
            
        except Exception as e:
            self.logger.error(f"Error during job cleanup: {str(e)}")
            raise

### Required Abstract Methods

1. **start()** - Main entry point for job execution
   - Must be implemented by all job subclasses
   - Should handle the main job logic
   - Responsible for state management (complete/fail)
   - Should be async to support long-running tasks

2. **stop_handler()** - Cleanup handler when job is stopped
   - Must be implemented by all job subclasses
   - Called automatically when job is stopped
   - Should clean up all resources
   - Must be async to support cleanup operations
   - Base class handles cancellation state after cleanup

### Job Lifecycle

1. **Creation**: Jobs are created with a unique ID and optional configuration
   ```python
   job = MyCustomJob("unique_id", config={"key": "value"})
   ```

2. **Starting**: The job is submitted to the JobManager which calls `start()`
   ```python
   job_id = await job_manager.submit_job(job)
   ```

3. **Running**: Job performs its main task in `start()`
   - Updates its status to `RUNNING`
   - Processes data
   - Can emit progress updates

4. **Completion**: Job ends in one of three states:
   - **Success**: Job calls `complete()` with results
     ```python
     self.complete(JobResult(success=True, message="Done", data=results))
     ```
   - **Failure**: Job calls `fail()` with error
     ```python
     self.fail("Operation failed: reason")
     ```
   - **Cancellation**: Job is stopped externally
     1. `stop_handler()` is called for cleanup
     2. Job is marked as `CANCELLED`

5. **Cleanup**: Resources are released
   - Automatic cleanup via `stop_handler()` when stopped
   - Manual cleanup in `start()` after completion

### Job Status

Jobs can be in one of these states:
- `PENDING`: Initial state after creation
- `RUNNING`: Job is actively processing
- `COMPLETED`: Job finished successfully
- `FAILED`: Job encountered an error
- `CANCELLED`: Job was stopped before completion

### Job Results

Jobs communicate results through the `JobResult` class:

```python
self.complete(JobResult(
    success=True,           # Whether the job succeeded
    message="Summary msg",  # Short summary message
    data={"key": "value"}, # Structured result data
    outputs=["out1", "out2"] # List of text outputs
))
```

### Example: Process Management

For jobs that spawn external processes:

```python
class ProcessJob(Job):
    def __init__(self, job_id: str):
        super().__init__(job_id)
        self._processes = []  # Track child processes
    
    async def start(self) -> None:
        try:
            process = subprocess.Popen(
                ["long-running-command"],
                stdout=subprocess.PIPE
            )
            self._processes.append(process)
            
            # Wait for completion
            stdout, _ = await process.communicate()
            
            self.complete(JobResult(
                success=True,
                message="Process completed",
                data={"output": stdout}
            ))
            
        except Exception as e:
            self.fail(str(e))
            
    async def stop_handler(self) -> None:
        """Clean up by killing child processes"""
        for process in self._processes:
            try:
                process.kill()
                await process.wait(timeout=5)
            except Exception as e:
                self.logger.error(f"Error killing process {process.pid}: {e}")
        self._processes.clear()
```

### Best Practices

1. **Resource Management**
   - Track all resources (processes, files, connections)
   - Clean up resources in `stop_handler`
   - Use context managers where possible

2. **State Management**
   - Update job status appropriately
   - Store results using `complete()`
   - Handle errors with `fail()`

3. **Error Handling**
   - Catch and log all exceptions
   - Clean up resources on failure
   - Provide meaningful error messages

4. **Progress Updates**
   - Log important state changes
   - Store intermediate results if useful
   - Consider adding progress tracking

5. **Configuration**
   - Accept configuration via constructor
   - Validate configuration early
   - Use sensible defaults

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