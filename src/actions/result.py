"""Action result types and formatting"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union, Iterator
from enum import Enum


class ResultType(Enum):
    """Types of action results"""

    TEXT = "text"  # Simple text message
    LIST = "list"  # List of items
    TABLE = "table"  # Tabular data
    TREE = "tree"  # Tree/hierarchical data
    JSON = "json"  # JSON data
    ERROR = "error"  # Error message


@dataclass
class ActionResult:
    """Result of an action execution"""

    type: ResultType
    content: Any  # The actual result content
    metadata: Optional[Dict[str, Any]] = None  # Additional metadata about the result
    error: Optional[str] = None  # Error message for error results

    def __str__(self) -> str:
        """String representation of the result"""
        if self.type == ResultType.ERROR:
            return f"Error: {self.error or self.content}"
        elif self.type == ResultType.TEXT:
            return str(self.content)
        elif self.type == ResultType.LIST:
            if not self.content:
                return "No items found."
            return "\n".join(f"• {str(item)}" for item in self.content)
        elif self.type == ResultType.TABLE:
            if not isinstance(self.content, dict) or "headers" not in self.content or "rows" not in self.content:
                return str(self.content)
            headers = self.content["headers"]
            rows = self.content["rows"]
            if not rows:
                return "No data found."
            lines = []
            # Format table
            widths = [len(str(h)) for h in headers]
            for row in rows:
                for i, cell in enumerate(row):
                    widths[i] = max(widths[i], len(str(cell)))
            header_line = " | ".join(str(h).ljust(w) for h, w in zip(headers, widths))
            lines.append(header_line)
            lines.append("-" * len(header_line))
            for row in rows:
                lines.append(" | ".join(str(cell).ljust(w) for cell, w in zip(row, widths)))
            return "\n".join(lines)
        elif self.type == ResultType.TREE:

            def format_tree(data: Dict[str, Any], level: int = 0) -> List[str]:
                lines = []
                indent = "  " * level
                for key, value in data.items():
                    if isinstance(value, dict):
                        lines.append(f"{indent}{key}:")
                        lines.extend(format_tree(value, level + 1))
                    elif isinstance(value, list):
                        lines.append(f"{indent}{key}:")
                        for item in value:
                            if isinstance(item, dict):
                                lines.extend(format_tree(item, level + 1))
                            else:
                                lines.append(f"{indent}  • {str(item)}")
                    else:
                        # Convert enum values to their string value
                        if hasattr(value, "value"):
                            value = value.value
                        lines.append(f"{indent}{key}: {str(value)}")
                return lines

            return "\n".join(format_tree(self.content))
        elif self.type == ResultType.JSON:
            import json

            return json.dumps(self.content, indent=2)
        else:
            return str(self.content)

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
