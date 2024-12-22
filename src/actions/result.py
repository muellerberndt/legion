"""Action result types and formatting"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union, Iterator
from enum import Enum
import json


class ResultType(Enum):
    """Types of action results"""

    TEXT = "text"  # Simple text message
    LIST = "list"  # List of items
    TABLE = "table"  # Tabular data
    TREE = "tree"  # Tree/hierarchical data
    JSON = "json"  # JSON data
    ERROR = "error"  # Error message
    JOB = "job"  # Async job launched


@dataclass
class ActionResult:
    """Result from an action execution"""

    type: ResultType
    content: str
    job_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def __str__(self) -> str:
        """String representation of the result"""
        if self.type == ResultType.TEXT:
            return str(self.content)
        elif self.type == ResultType.TREE:
            return json.dumps(self.content, indent=2)
        elif self.type == ResultType.JOB:
            return f"Job started: {self.job_id}"
        elif self.type == ResultType.ERROR:
            return f"Error: {self.error}"
        return str(self.content)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "type": self.type.value,  # Convert enum to string
            "content": self.content,
            "job_id": self.job_id,
            "metadata": self.metadata,
        }

    def __json__(self) -> Dict[str, Any]:
        """JSON serialization support"""
        return self.to_dict()

    def __contains__(self, item: str) -> bool:
        """Support 'in' operator by checking if the string is in the string representation"""
        return item in str(self)

    def __iter__(self) -> Iterator[str]:
        """Make the result iterable by yielding lines from its string representation"""
        yield from str(self).split("\n")

    @staticmethod
    def text(content: str) -> "ActionResult":
        """Create a text result"""
        return ActionResult(type=ResultType.TEXT, content=content)

    @staticmethod
    def list(items: List[Any], metadata: Optional[Dict[str, Any]] = None) -> "ActionResult":
        """Create a list result"""
        return ActionResult(type=ResultType.LIST, content=items, metadata=metadata)

    @staticmethod
    def table(headers: List[str], rows: List[List[Any]], metadata: Optional[Dict[str, Any]] = None) -> "ActionResult":
        """Create a table result"""
        return ActionResult(type=ResultType.TABLE, content={"headers": headers, "rows": rows}, metadata=metadata)

    @staticmethod
    def tree(data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> "ActionResult":
        """Create a tree result"""
        return ActionResult(type=ResultType.TREE, content=data, metadata=metadata)

    @staticmethod
    def json(data: Union[Dict[str, Any], List[Any]], metadata: Optional[Dict[str, Any]] = None) -> "ActionResult":
        """Create a JSON result"""
        return ActionResult(type=ResultType.JSON, content=data, metadata=metadata)

    @staticmethod
    def error(message: str, metadata: Optional[Dict[str, Any]] = None) -> "ActionResult":  # noqa: F811
        """Create an error result"""
        return ActionResult(type=ResultType.ERROR, content=message, error=message, metadata=metadata)

    @staticmethod
    def job(job_id: str, metadata: Optional[Dict[str, Any]] = None) -> "ActionResult":
        """Create a job result"""
        return ActionResult(type=ResultType.JOB, content=f"Started job {job_id}", job_id=job_id, metadata=metadata)
