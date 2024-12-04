from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import asyncio
from src.jobs.base import Job, JobType, JobResult
from src.util.logging import Logger
from src.handlers.base import HandlerTrigger
from src.handlers.event_bus import EventBus

class WatcherJob(Job, ABC):
    """Base class for watcher jobs that monitor external states"""
    
    def __init__(self, name: str, interval: int = 60):
        """Initialize the watcher
        
        Args:
            name: Name of the watcher for logging
            interval: Check interval in seconds
        """
        super().__init__(JobType.WATCHER)
        self.name = name
        self.interval = interval
        self.logger = Logger(f"Watcher-{name}")
        self.event_bus = EventBus()
        self._stop_event = asyncio.Event()
        self._last_check: Optional[datetime] = None
        self._state: Dict[str, Any] = {}  # Store watcher state
        
    @abstractmethod
    async def check(self) -> List[Dict[str, Any]]:
        """Check for updates and return list of events
        
        Returns:
            List of event dictionaries with at least:
            - trigger: HandlerTrigger enum value
            - data: Dict of event data
        """
        pass
        
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize watcher state"""
        pass
        
    async def start(self) -> None:
        """Start the watcher loop"""
        try:
            self.result = JobResult(success=True, message=f"Watcher {self.name} started")
            
            # Initialize watcher
            await self.initialize()
            self._last_check = datetime.utcnow()
            
            # Start the watch loop in a background task
            self.logger.info(f"Starting watcher loop for {self.name}")
            asyncio.create_task(self._watch_loop())
            
        except Exception as e:
            error_msg = f"Watcher failed: {str(e)}"
            self.logger.error(error_msg)
            if self.result:
                self.result.success = False
                self.result.message = error_msg
            else:
                self.result = JobResult(success=False, message=error_msg)
                
    async def _watch_loop(self) -> None:
        """Background task for the watch loop"""
        while not self._stop_event.is_set():
            try:
                # Check for updates
                events = await self.check()
                
                # Process events
                for event in events:
                    trigger = event.get('trigger')
                    data = event.get('data', {})
                    
                    if trigger and isinstance(trigger, HandlerTrigger):
                        # Trigger handlers
                        self.event_bus.trigger_event(trigger, data)
                        
                        # Log event
                        self.result.add_output(
                            f"Event detected - Trigger: {trigger.name}, "
                            f"Data: {str(data)}"
                        )
                        
                # Update last check time
                self._last_check = datetime.utcnow()
                
            except Exception as e:
                self.logger.error(f"Error in watch cycle: {str(e)}")
                
            # Wait for next check or stop signal
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.interval
                )
            except asyncio.TimeoutError:
                continue
                
    async def stop(self) -> None:
        """Stop the watcher"""
        self._stop_event.set()
        
    def get_state(self) -> Dict[str, Any]:
        """Get current watcher state"""
        return {
            'name': self.name,
            'last_check': self._last_check.isoformat() if self._last_check else None,
            'running': not self._stop_event.is_set(),
            'state': self._state
        } 