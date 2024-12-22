"""Utilities for formatting action results"""

from src.actions.result import ActionResult, ResultType


class ActionResultFormatter:
    """Formats ActionResults into different output formats"""

    @staticmethod
    def to_html(result: ActionResult) -> str:
        """Format an ActionResult as HTML"""
        if result.type == ResultType.TEXT:
            return f"<pre>{result.content}</pre>"

        elif result.type == ResultType.ERROR:
            return f'<div class="error"><strong>Error:</strong> {result.content}</div>'

        elif result.type == ResultType.TREE:
            return ActionResultFormatter._format_tree_html(result.content)

        elif result.type == ResultType.TABLE:
            return ActionResultFormatter._format_table_html(result.content)

        return f"<pre>Unknown result type: {result.content}</pre>"

    @staticmethod
    def _format_tree_html(data: dict, level: int = 0) -> str:
        """Format a tree structure as nested HTML lists"""
        if not isinstance(data, dict):
            return str(data)

        items = []
        for key, value in data.items():
            if isinstance(value, dict):
                items.append(
                    f"<li><strong>{key}:</strong><ul>{ActionResultFormatter._format_tree_html(value, level + 1)}</ul></li>"
                )
            else:
                items.append(f"<li><strong>{key}:</strong> {value}</li>")

        return f"<ul>{''.join(items)}</ul>" if items else ""

    @staticmethod
    def _format_table_html(data: list) -> str:
        """Format tabular data as an HTML table"""
        if not data or not isinstance(data, list):
            return "<p>No data</p>"

        headers = data[0].keys() if data else []
        rows = []

        # Add header row
        header_row = "".join(f"<th>{h}</th>" for h in headers)
        rows.append(f"<tr>{header_row}</tr>")

        # Add data rows
        for row in data:
            cells = "".join(f"<td>{row.get(h, '')}</td>" for h in headers)
            rows.append(f"<tr>{cells}</tr>")

        return f"<table border='1'>{''.join(rows)}</table>"
