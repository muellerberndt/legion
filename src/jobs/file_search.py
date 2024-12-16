from src.jobs.base import Job, JobResult
from src.backend.database import DBSessionMixin
from src.util.logging import Logger
import os
import re
from typing import List, Dict
from src.models.base import Asset
import asyncio
from src.config.config import Config


def is_binary_file(file_path: str) -> bool:
    """Check if a file is binary by reading its first few bytes"""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            if not chunk:  # Empty file
                return False
            # Check for null bytes and high concentration of non-text bytes
            textchars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7F})
            return bool(chunk.translate(None, textchars))
    except Exception:
        return True


class FileSearchJob(Job, DBSessionMixin):
    """Job to search local files using regex and retrieve associated asset info"""

    # File extensions to skip
    SKIP_EXTENSIONS = {
        ".zip",
        ".gz",
        ".tar",
        ".rar",
        ".7z",  # Archives
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".ico",  # Images
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",  # Documents
        ".bin",
        ".exe",
        ".dll",
        ".so",
        ".dylib",  # Binaries
        ".pyc",
        ".pyo",
        ".pyd",  # Python bytecode
        ".class",  # Java bytecode
        ".o",  # Object files
        ".lock",
        ".lockb",  # Lock files
    }

    def __init__(self, regex_pattern: str):
        Job.__init__(self, job_type="file_search")
        DBSessionMixin.__init__(self)
        self.logger = Logger("FileSearchJob")
        # Compile regex pattern to match parts of words
        self.pattern = re.compile(regex_pattern, re.IGNORECASE | re.MULTILINE)

        # Get allowed extensions from config
        config = Config()
        self.allowed_extensions = set(
            config.get("file_search.allowed_extensions", [".sol", ".cairo", ".rs", ".vy", ".fe", ".move", ".yul"])
        )
        self.logger.info(f"Using allowed extensions: {self.allowed_extensions}")

    def _should_skip_file(self, file_path: str) -> bool:
        """Check if we should skip this file"""
        _, ext = os.path.splitext(file_path.lower())
        # Skip if extension is in skip list or if we have allowed extensions and this isn't one of them
        return ext in self.SKIP_EXTENSIONS or (self.allowed_extensions and ext not in self.allowed_extensions)

    def _search_file(self, file_path: str, pattern: re.Pattern) -> List[Dict]:
        """Search a single file for regex matches"""
        try:
            # Skip binary and known binary extensions
            if self._should_skip_file(file_path) or is_binary_file(file_path):
                return []

            # Read file content
            with open(file_path, "r") as f:
                content = f.read()

            # Use finditer to get non-overlapping matches with positions
            matches = list(pattern.finditer(content))
            file_matches = []

            for match in matches:
                self.logger.debug(f"Match: {match.group(0)}")
                # Get some context around the match
                start = max(0, match.start() - 50)
                end = min(len(content), match.end() + 50)
                context = content[start:end]

                # Get the match info - we want to match any occurrence of the pattern
                match_info = {"match": match.group(0), "context": context, "start": match.start(), "end": match.end()}
                file_matches.append(match_info)

            return file_matches

        except Exception as e:
            self.logger.error(f"Error searching file {file_path}: {str(e)}")
            return []

    def _search_directory(self, directory: str, pattern: re.Pattern) -> List[Dict]:
        """Recursively search a directory for regex matches"""
        matches = []
        try:
            for root, _, files in os.walk(directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        file_matches = self._search_file(file_path, pattern)
                        if file_matches:
                            matches.append({"file_path": file_path, "matches": file_matches})
                    except Exception as e:
                        self.logger.error(f"Error processing file {file_path}: {str(e)}")
                        continue
        except Exception as e:
            self.logger.error(f"Error searching directory {directory}: {str(e)}")
            return []
        return matches

    async def _search_file_async(self, file_path: str, pattern: re.Pattern) -> List[Dict]:
        """Search a single file for regex matches asynchronously"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._search_file, file_path, pattern)

    async def _search_directory_async(self, directory: str, pattern: re.Pattern) -> List[Dict]:
        """Recursively search a directory for regex matches asynchronously"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._search_directory, directory, pattern)

    async def start(self) -> None:
        """Start the file search job"""
        try:
            # Get config
            config = Config.get()
            allowed_extensions = config.get("file_search", {}).get("allowed_extensions", [])

            # Get search parameters
            pattern = self.config.get("pattern")
            if not pattern:
                await self.fail("No search pattern provided")
                return

            # Initialize results
            results = []
            total_matches = 0
            max_outputs = 100  # Limit number of outputs to prevent context length issues

            # Get all assets from database
            with self.get_session() as session:
                assets = session.query(Asset).all()
                self.logger.info(f"Searching {len(assets)} assets")

                # Search each asset
                for asset in assets:
                    # Skip if no local path
                    if not asset.local_path:
                        continue

                    # Get all files in asset directory
                    try:
                        files = []
                        for root, _, filenames in os.walk(asset.local_path):
                            for filename in filenames:
                                # Skip if extension not allowed
                                if allowed_extensions and not any(filename.endswith(ext) for ext in allowed_extensions):
                                    continue
                                files.append(os.path.join(root, filename))
                    except Exception as e:
                        self.logger.error(f"Error listing files for {asset.local_path}: {str(e)}")
                        continue

                    # Search each file
                    asset_matches = []
                    for file_path in files:
                        try:
                            # Skip binary files
                            if self._is_binary_file(file_path):
                                continue

                            # Get relative path
                            rel_path = os.path.relpath(file_path, asset.local_path)

                            # Search file
                            matches = []
                            with open(file_path, "r", encoding="utf-8") as f:
                                for i, line in enumerate(f, 1):
                                    if pattern in line:
                                        # Get context (3 lines before and after)
                                        context = self._get_context(file_path, i)
                                        matches.append(
                                            {
                                                "line": i,
                                                "match": line.strip(),
                                                "context": context,
                                            }
                                        )
                                        total_matches += 1

                            if matches:
                                asset_matches.append({"file_path": rel_path, "matches": matches})

                        except Exception as e:
                            self.logger.error(f"Error searching file {file_path}: {str(e)}")
                            continue

                    if asset_matches:
                        results.append(
                            {
                                "asset": {
                                    "id": asset.id,
                                    "source_url": asset.source_url,
                                    "asset_type": asset.asset_type,
                                },
                                "matches": asset_matches,
                            }
                        )

            # Create result with outputs
            result = JobResult(
                success=True, message=f"Found {total_matches} matches across {len(results)} assets", data={"results": results}
            )

            # Add outputs with limit
            output_count = 0
            for asset_result in results:
                if output_count >= max_outputs:
                    result.add_output(f"\n... truncated ({total_matches - output_count} more matches) ...")
                    break

                asset = asset_result["asset"]
                for file_match in asset_result["matches"]:
                    if output_count >= max_outputs:
                        break
                    file_path = file_match["file_path"]
                    for match in file_match["matches"]:
                        if output_count >= max_outputs:
                            break
                        output = (
                            f"Match in {asset['source_url']} ({asset['asset_type']}):\n"
                            f"Source: {asset['source_url']}\n"
                            f"File: {file_path}\n"
                            f"Match: {match['match']}\n"
                            f"Context: {match['context']}\n"
                        )
                        result.add_output(output)
                        output_count += 1

            # Complete the job with results
            await self.complete(result)

        except Exception as e:
            self.logger.error(f"Error in file search: {str(e)}")
            await self.fail(str(e))

    async def stop_handler(self) -> None:
        """Stop the job - nothing to do for search"""
