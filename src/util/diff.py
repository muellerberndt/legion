from typing import List, Tuple, Optional
import difflib
import aiofiles
from src.util.logging import Logger


class DiffResult:
    """Result of a diff operation"""

    def __init__(
        self,
        old_path: str,
        new_path: str,
        added_lines: List[Tuple[int, str]],
        removed_lines: List[Tuple[int, str]],
        modified_lines: List[Tuple[int, int, str, str]],
    ):
        self.old_path = old_path
        self.new_path = new_path
        self.added_lines = added_lines  # [(line_number, content), ...]
        self.removed_lines = removed_lines  # [(line_number, content), ...]
        self.modified_lines = modified_lines  # [(old_line, new_line, old_content, new_content), ...]

    @property
    def has_changes(self) -> bool:
        """Check if there are any changes"""
        return bool(self.added_lines or self.removed_lines or self.modified_lines)

    def to_unified_diff(self) -> str:
        """Convert to unified diff format"""
        lines = [f"--- {self.old_path}", f"+++ {self.new_path}", ""]

        # Add removed lines
        for line_num, content in self.removed_lines:
            lines.append(f"-{line_num}: {content}")

        # Add added lines
        for line_num, content in self.added_lines:
            lines.append(f"+{line_num}: {content}")

        # Add modified lines
        for old_line, new_line, old_content, new_content in self.modified_lines:
            lines.append(f"-{old_line}: {old_content}")
            lines.append(f"+{new_line}: {new_content}")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Convert to dictionary format"""
        return {
            "old_path": self.old_path,
            "new_path": self.new_path,
            "added_lines": self.added_lines,
            "removed_lines": self.removed_lines,
            "modified_lines": self.modified_lines,
        }


async def compute_file_diff(old_path: str, new_path: str) -> Optional[DiffResult]:
    """Compute diff between two files"""
    try:
        # Read old file
        async with aiofiles.open(old_path, "r") as f:
            old_content = await f.read()
        old_lines = old_content.splitlines()

        # Read new file
        async with aiofiles.open(new_path, "r") as f:
            new_content = await f.read()
        new_lines = new_content.splitlines()

        # Generate diff using difflib
        differ = difflib.SequenceMatcher(None, old_lines, new_lines)

        added_lines = []
        removed_lines = []
        modified_lines = []

        for tag, i1, i2, j1, j2 in differ.get_opcodes():
            if tag == "insert":
                # Lines were added
                for i in range(j1, j2):
                    added_lines.append((i + 1, new_lines[i]))
            elif tag == "delete":
                # Lines were removed
                for i in range(i1, i2):
                    removed_lines.append((i + 1, old_lines[i]))
            elif tag == "replace":
                # Lines were modified
                # Try to match up lines that were modified
                min_len = min(i2 - i1, j2 - j1)
                for k in range(min_len):
                    modified_lines.append(
                        (
                            i1 + k + 1,  # old line number
                            j1 + k + 1,  # new line number
                            old_lines[i1 + k],  # old content
                            new_lines[j1 + k],  # new content
                        )
                    )

                # Handle any remaining lines as adds/removes
                for i in range(i1 + min_len, i2):
                    removed_lines.append((i + 1, old_lines[i]))
                for j in range(j1 + min_len, j2):
                    added_lines.append((j + 1, new_lines[j]))

        return DiffResult(
            old_path=old_path,
            new_path=new_path,
            added_lines=added_lines,
            removed_lines=removed_lines,
            modified_lines=modified_lines,
        )

    except Exception as e:
        # Log error but don't fail - diff is non-critical
        Logger("DiffUtil").error(f"Failed to compute diff: {str(e)}")
        return None
