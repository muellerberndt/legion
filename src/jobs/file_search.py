from src.jobs.base import Job, JobResult
from src.backend.database import DBSessionMixin
from src.util.logging import Logger
import os
import re
from typing import List, Dict
from src.models.base import Asset
from sqlalchemy import select
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
        # Compile regex pattern - add word boundaries to match whole words
        self.pattern = re.compile(re.escape(regex_pattern), re.IGNORECASE)

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
                # Get some context around the match
                start = max(0, match.start() - 50)
                end = min(len(content), match.end() + 50)
                context = content[start:end]

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
        """Execute the file search job"""
        try:
            # self.status = JobStatus.RUNNING
            results = []
            total_matches = 0
            processed_paths = set()  # Keep track of processed file paths

            # Get all assets with local paths from database
            with self.get_session() as session:
                stmt = select(Asset).where(Asset.local_path.isnot(None))
                assets = session.execute(stmt).scalars().all()
                path_to_asset = {asset.local_path: asset for asset in assets}
                self.logger.debug(f"Found {len(path_to_asset)} assets to search")

            self.logger.debug(f"Using search pattern: {self.pattern.pattern}")

            # Search through assets
            for local_path, asset in path_to_asset.items():
                if not os.path.exists(local_path):
                    self.logger.debug(f"Skipping non-existent path: {local_path}")
                    continue

                try:
                    asset_matches = []
                    # Handle both files and directories
                    if os.path.isfile(local_path):
                        if local_path not in processed_paths:
                            processed_paths.add(local_path)
                            file_matches = await self._search_file_async(local_path, self.pattern)
                            if file_matches:
                                self.logger.debug(f"Found {len(file_matches)} matches in file: {local_path}")
                                asset_matches.append({"file_path": local_path, "matches": file_matches})
                    else:  # Directory
                        self.logger.debug(f"Searching directory: {local_path}")
                        dir_matches = await self._search_directory_async(local_path, self.pattern)
                        for dir_match in dir_matches:
                            file_path = dir_match["file_path"]
                            if file_path not in processed_paths:
                                processed_paths.add(file_path)
                                self.logger.debug(f"Found {len(dir_match['matches'])} matches in: {file_path}")
                                asset_matches.append(dir_match)

                    # Only add asset to results if it has matches
                    if asset_matches:
                        # Count matches
                        file_match_count = sum(len(file_match["matches"]) for file_match in asset_matches)
                        total_matches += file_match_count
                        self.logger.debug(f"Asset {asset.id} has {file_match_count} matches in {len(asset_matches)} files")
                        results.append(
                            {
                                "asset": {
                                    "id": asset.id,
                                    "asset_type": asset.asset_type,
                                    "source_url": asset.source_url,
                                    "extra_data": asset.extra_data,
                                },
                                "matches": asset_matches,
                            }
                        )

                except Exception as e:
                    self.logger.error(f"Error processing asset {local_path}: {str(e)}")
                    continue

            self.logger.info(f"Search complete: {total_matches} matches in {len(results)} assets")
            self.logger.debug(f"Processed {len(processed_paths)} unique files")

            # Create result with outputs
            result = JobResult(
                success=True, message=f"Found {total_matches} matches across {len(results)} assets", data={"results": results}
            )

            # Add all outputs without limiting
            for asset_result in results:
                asset = asset_result["asset"]
                for file_match in asset_result["matches"]:
                    file_path = file_match["file_path"]
                    for match in file_match["matches"]:
                        output = (
                            f"Match in {asset['source_url']} ({asset['asset_type']}):\n"
                            f"Source: {asset['source_url']}\n"
                            f"File: {file_path}\n"
                            f"Match: {match['match']}\n"
                            f"Context: {match['context']}\n"
                        )
                        result.add_output(output)

            # Complete the job with results
            await self.complete(result)

        except Exception as e:
            self.logger.error(f"Error in file search: {str(e)}")
            await self.fail(str(e))

    async def stop_handler(self) -> None:
        """Stop the job - nothing to do for search"""
