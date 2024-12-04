from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.handlers.base import Handler, HandlerTrigger
from src.jobs.watcher import WatcherJob
from datetime import datetime

class HelloAction(BaseAction):
    """Example custom action"""
    
    spec = ActionSpec(
        name="hello",
        description="Say hello",
        arguments=[
            ActionArgument(name="name", description="Name to greet", required=False)
        ]
    )
    
    async def execute(self, name: str = "World") -> str:
        return f"Hello, {name}!"

class ExampleHandler(Handler):
    """Example custom handler"""
    
    @classmethod
    def get_triggers(cls) -> list[HandlerTrigger]:
        return [HandlerTrigger.NEW_PROJECT]
    
    def handle(self) -> None:
        project = self.context.get('project')

class ExampleWatcher(WatcherJob):
    """Example custom watcher"""
    
    def __init__(self):
        super().__init__("example", interval=60)
        
    async def initialize(self) -> None:
        """Initialize watcher state"""
        self._state['last_time'] = None
        
    async def check(self) -> list[dict]:
        """Check for updates"""
        current_time = datetime.utcnow()
        last_time = self._state.get('last_time')
        self._state['last_time'] = current_time
        
        if last_time:
            return [{
                'trigger': HandlerTrigger.NEW_PROJECT,
                'data': {'message': f"Time elapsed: {current_time - last_time}"}
            }]
        
        return [] 