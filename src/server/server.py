import asyncio
import signal
from typing import Dict, List
from src.jobs.manager import JobManager
from src.watchers.manager import WatcherManager
from src.handlers.registry import HandlerRegistry
from src.util.logging import Logger
from src.config.config import Config
from src.interfaces.base import Interface
from src.interfaces.telegram import TelegramInterface
from src.actions.registry import ActionRegistry
import concurrent.futures
import threading

class Server:
    """Main server that manages jobs, watchers, and handlers"""
    
    def __init__(self):
        self.logger = Logger("Server")
        self.config = Config()
        self.job_manager = JobManager()
        self.watcher_manager = WatcherManager()
        self.handler_registry = HandlerRegistry()
        self.action_registry = ActionRegistry()
        self.interfaces: Dict[str, Interface] = {}
        self.shutdown_event = asyncio.Event()
        self.shutting_down = False
        
    async def start(self, enabled_interfaces: List[str] = ['telegram']) -> None:
        """Start the server and all its components"""
        self.logger.info("Starting server...")
        
        # Register signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.handle_signal(s)))
            
        try:
            # Initialize interfaces
            if 'telegram' in enabled_interfaces:
                telegram = TelegramInterface(action_registry=self.action_registry)
                self.interfaces['telegram'] = telegram
                await telegram.start()
                self.logger.info("Started Telegram interface")
            
            # Start job manager
            await self.job_manager.start()
            
            # Start watcher manager if enabled
            if self.config.get("watchers", {}).get("enabled", True):
                await self.watcher_manager.start()
                
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
        except Exception as e:
            self.logger.error(f"Server error: {e}")
            raise
        finally:
            # Ensure cleanup happens even on error
            await self.shutdown()
            
    async def handle_signal(self, sig: signal.Signals) -> None:
        """Handle shutdown signals"""
        if self.shutting_down:
            self.logger.warning("Received another shutdown signal, forcing immediate shutdown")
            # Clear any remaining thread pools
            concurrent.futures.thread._threads_queues.clear()
            if hasattr(threading, '_threads'):
                threading._threads.clear()
            return
            
        self.logger.info(f"Received signal {sig.name}, initiating shutdown...")
        self.shutdown_event.set()
            
    async def shutdown(self) -> None:
        """Gracefully shutdown the server"""
        if self.shutting_down:
            return
            
        self.shutting_down = True
        self.logger.info("Shutting down server...")
        
        shutdown_tasks = []
        
        try:
            # Stop interfaces first
            for name, interface in self.interfaces.items():
                self.logger.info(f"Stopping interface: {name}")
                shutdown_tasks.append(interface.stop())
            
            # Stop watchers
            shutdown_tasks.append(self.watcher_manager.stop())
            
            # Stop job manager
            shutdown_tasks.append(self.job_manager.stop())
            
            # Wait for all shutdown tasks with timeout
            if shutdown_tasks:
                try:
                    await asyncio.wait_for(asyncio.gather(*shutdown_tasks), timeout=5.0)
                except asyncio.TimeoutError:
                    self.logger.error("Some components did not shut down gracefully")
                    
            # Clear any remaining thread pools
            concurrent.futures.thread._threads_queues.clear()
            if hasattr(threading, '_threads'):
                threading._threads.clear()
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
        
    @classmethod
    async def run(cls, enabled_interfaces: List[str] = ['telegram']) -> None:
        """Run the server"""
        server = cls()
        try:
            await server.start(enabled_interfaces)
        except KeyboardInterrupt:
            await server.shutdown()
