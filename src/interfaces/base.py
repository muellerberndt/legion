from abc import ABC, abstractmethod
from typing import List

class Message:
    """Message object for communication between components"""
    
    def __init__(self, session_id: str, content: str, arguments: List[str] = None):
        self.session_id = session_id
        self.content = content
        self.arguments = arguments or []

class Interface(ABC):
    """Base class for all interfaces"""
    
    @abstractmethod
    async def start(self) -> None:
        """Start the interface"""
        pass
        
    @abstractmethod
    async def stop(self) -> None:
        """Stop the interface"""
        pass
        
    @abstractmethod
    async def handle_message(self, content: str, session_id: str) -> None:
        """Handle a message"""
        pass
        
    @abstractmethod
    async def send_message(self, content: str, session_id: str) -> None:
        """Send a message"""
        pass 