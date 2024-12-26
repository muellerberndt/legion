# Customization Guide

Legion is designed to be highly extensible through its extension system. At its core, Legion provides a framework where custom functionality can be added through three main concepts: Actions, Jobs, and Handlers. Each of these serves a distinct purpose in the system, and understanding how they work together is key to creating effective extensions.

## Understanding Actions

Actions form the foundation of Legion's extensibility. An action represents a discrete piece of functionality that can be invoked directly by users through Telegram commands or utilized by AI agents in their decision-making processes. What makes actions particularly powerful is their dual nature - they serve both as user commands and as tools that AI agents can reason about and employ.

When creating an action, you'll define both its behavior and its interface through the ActionSpec system. The specification tells Legion how the action should be presented to users, what arguments it accepts, and provides crucial hints to AI agents about when and how to use the action. Here's how you might create a new action:

```python
from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.actions.result import ActionResult
from src.util.logging import Logger

class DataAnalysisAction(BaseAction):
    """Analyzes data sets and provides statistical insights"""
    
    spec = ActionSpec(
        name="analyze",
        description="Analyze a dataset for patterns and anomalies",
        help_text="Performs statistical analysis on provided data",
        agent_hint="Use this when you need to understand patterns in numerical data",
        arguments=[
            ActionArgument(
                name="dataset",
                description="Path to the dataset to analyze",
                required=True
            )
        ]
    )
    
    async def execute(self, dataset: str) -> ActionResult:
        """Execute the analysis"""
        try:
            # Your analysis logic here
            results = self._perform_analysis(dataset)
            
            # Return results using ActionResult
            return ActionResult.json(
                data=results,
                metadata={"dataset": dataset}
            )
            
        except Exception as e:
            return ActionResult.error(f"Analysis failed: {str(e)}")
```

The ActionResult system provides a structured way to return data from your actions. Rather than returning raw strings or dictionaries, Legion uses ActionResult objects to maintain consistency and provide rich formatting options. The system supports several result types:

- Text results for simple messages
- JSON results for structured data
- Table results for grid-like data
- Tree results for hierarchical information
- Error results for failure cases
- Job results for long-running operations

Each result type can include metadata to provide additional context about the operation. This metadata is particularly useful for AI agents that might need to understand more about the result's context or make decisions based on the operation's outcome.

When your action needs to perform long-running operations, you'll want to consider using the Job system. Jobs allow actions to initiate background tasks while immediately returning feedback to the user. For example:

```python
async def execute(self, dataset: str) -> ActionResult:
    """Execute the analysis as a background job"""
    try:
        # Create and submit a job
        job = AnalysisJob(dataset=dataset)
        job_id = await self.job_manager.submit_job(job)
        
        # Return a job result that users can track
        return ActionResult.job(
            job_id=job_id,
            metadata={"dataset": dataset}
        )
        
    except Exception as e:
        return ActionResult.error(f"Failed to start analysis: {str(e)}")
```

## Understanding Jobs

While actions provide immediate responses to commands, many operations in Legion require longer processing times. The Job system addresses this need by providing a framework for background tasks that can run asynchronously while keeping users informed of their progress. Jobs are particularly useful for operations like data analysis, security scans, or blockchain monitoring that might take several seconds or even minutes to complete.

When you create a job, you're defining a self-contained unit of work that can report its progress and manage its own lifecycle. Here's how you might implement a job for analyzing blockchain transactions:

```python
from src.jobs.base import Job, JobResult
from src.util.logging import Logger

class BlockchainAnalysisJob(Job):
    """Analyzes blockchain transactions for patterns"""
    
    def __init__(self, address: str, block_range: int):
        super().__init__(job_type="blockchain_analysis")
        self.address = address
        self.block_range = block_range
        self.logger = Logger("BlockchainAnalysisJob")
    
    async def start(self) -> None:
        """Execute the analysis"""
        try:
            # Inform user that analysis is starting
            result = JobResult(success=True, message="Starting blockchain analysis...")
            result.add_output(f"Analyzing address {self.address}")
            result.add_output(f"Block range: {self.block_range}")
            
            # Perform the analysis in steps
            transactions = await self._fetch_transactions()
            result.add_output(f"Found {len(transactions)} transactions")
            
            patterns = await self._analyze_patterns(transactions)
            result.add_output("Pattern analysis complete")
            
            # Complete the job with full results
            await self.complete(JobResult(
                success=True,
                message="Analysis complete",
                data={
                    "address": self.address,
                    "transactions": len(transactions),
                    "patterns": patterns
                }
            ))
            
        except Exception as e:
            await self.fail(f"Analysis failed: {str(e)}")
    
    async def stop_handler(self) -> None:
        """Clean up resources when job is stopped"""
        # Cancel any pending blockchain requests
        # Close network connections
        # etc.
```

The JobResult system works hand-in-hand with Jobs to provide structured output that can be displayed to users or processed by other components. Unlike ActionResult, which is designed for immediate responses, JobResult is built to accumulate output over time and provide detailed progress information. You can add output lines as your job progresses, and these will be available to users who check the job's status.

## Event Handling with Handlers

The Handler system in Legion provides a way to react to events that occur within the system. While Actions respond to direct commands and Jobs handle long-running tasks, Handlers process events asynchronously as they occur. This makes them perfect for monitoring and responding to system events, blockchain activities, or external webhooks.

Handlers are registered to respond to specific triggers, and they can process events in whatever way makes sense for your use case. Here's an example of a handler that monitors for smart contract upgrades:

```python
from src.handlers.base import Handler, HandlerTrigger, HandlerResult
from src.util.logging import Logger

class ContractUpgradeHandler(Handler):
    """Monitors and responds to smart contract upgrades"""
    
    def __init__(self):
        super().__init__()
        self.logger = Logger("ContractUpgradeHandler")
    
    @classmethod
    def get_triggers(cls) -> list[HandlerTrigger]:
        """Define which events to handle"""
        return [HandlerTrigger.BLOCKCHAIN_EVENT]
    
    async def handle(self) -> HandlerResult:
        """Process a contract upgrade event"""
        try:
            # Extract event data from context
            event = self.context.get("event")
            if not self._is_upgrade_event(event):
                return HandlerResult(success=True)
            
            # Process the upgrade
            old_implementation = self._get_old_implementation(event)
            new_implementation = self._get_new_implementation(event)
            
            # Analyze the changes
            changes = await self._analyze_implementation_changes(
                old_implementation, 
                new_implementation
            )
            
            # Return the analysis results
            return HandlerResult(
                success=True,
                data={
                    "contract": event.get("address"),
                    "old_implementation": old_implementation,
                    "new_implementation": new_implementation,
                    "changes": changes
                }
            )
            
        except Exception as e:
            self.logger.error(f"Failed to process upgrade: {str(e)}")
            return HandlerResult(
                success=False,
                data={"error": str(e)}
            )
```

## Extension Loading and Registration

Legion uses a sophisticated extension loading system that automatically discovers and registers your custom components. Understanding how this system works will help you debug any issues and structure your extensions effectively.

### How Extension Loading Works

When Legion starts up, it scans the configured extensions directory for Python modules. The extension loader follows a specific process to ensure all components are properly discovered and registered:

```python
# In your config.yml
extensions_dir: "./extensions"
active_extensions:
  - my_extension
  - analysis_tools.blockchain
```

The loader first converts these extension paths into filesystem paths. For example, `analysis_tools.blockchain` would map to `./extensions/analysis_tools/blockchain/`. It then processes each Python file it finds, looking for classes that inherit from Legion's base components.

Here's what happens behind the scenes:

1. The loader imports each Python module it finds
2. It scans the module for classes that inherit from `BaseAction`, `Handler`, or `WebhookHandler`
3. For each discovered class:
   - Actions are registered with the `ActionRegistry`
   - Handlers are registered with the `HandlerRegistry`
   - Webhook handlers are registered with the `WebhookServer`

If you're having trouble with extension loading, you can enable debug logging to see exactly what's happening:

```python
# In your extension
from src.util.logging import Logger

logger = Logger("MyExtension")
logger.debug("Loading my extension...")
```

### Automatic Registration

When you create a new action or handler, you don't need to manually register it anywhere. Simply defining the class in a module within your extension directory is enough:

```python
# extensions/my_extension/actions.py
from src.actions.base import BaseAction, ActionSpec

class MyCustomAction(BaseAction):
    """This action will be automatically discovered and registered"""
    
    spec = ActionSpec(
        name="custom",
        description="My custom action",
        help_text="Detailed help text",
        agent_hint="Use this when you need to...",
        arguments=[]
    )
    
    async def execute(self) -> ActionResult:
        return ActionResult.text("Hello from custom action!")
```

The extension loader will find this class, verify it has the required attributes (like `spec` for actions), and register it with the appropriate registry. If something is missing or incorrectly configured, you'll see warning messages in the logs.

### Debugging Extension Issues

If your extension isn't working as expected, there are several places to look:

1. **Extension Loading Logs**: Check if your extension was found and loaded:
   ```
   [INFO] ExtensionLoader: Loading extensions from ./extensions: ['my_extension']
   [DEBUG] ExtensionLoader: Found class MyCustomAction in module extensions.my_extension.actions
   ```

2. **Component Registration**: Verify your components were registered:
   ```
   [INFO] ActionRegistry: Registered action: custom
   [INFO] HandlerRegistry: Registered handler: MyCustomHandler
   ```

3. **Runtime Errors**: Look for errors during component execution:
   ```
   [ERROR] MyCustomAction: Failed to execute: Invalid argument
   ```

The most common issues are:
- Missing or incorrect `spec` attribute on actions
- Forgetting to implement required methods
- Import errors due to incorrect module structure
- Type mismatches in method signatures

### Best Practices for Extensions

When creating extensions, following these practices will help ensure smooth operation:

1. **Module Structure**: Keep your extension's code organized:
   ```
   extensions/
     my_extension/
       __init__.py      # Can be empty
       actions.py       # Custom actions
       handlers.py      # Event handlers
       jobs.py         # Background jobs
       utils.py        # Helper functions
   ```

2. **Error Handling**: Always use try/except blocks and return appropriate results:
   ```python
   async def execute(self) -> ActionResult:
       try:
           result = await self._do_work()
           return ActionResult.json(result)
       except Exception as e:
           self.logger.error(f"Failed: {str(e)}")
           return ActionResult.error(str(e))
   ```

3. **Documentation**: Document your components thoroughly:
   ```python
   class DataAnalyzer(BaseAction):
       """Analyzes data sets for patterns and anomalies.
       
       This action processes input data using statistical methods
       to identify patterns, outliers, and trends
```
