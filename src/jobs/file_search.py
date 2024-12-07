from src.jobs.base import Job, JobType, JobResult, JobStatus
from src.backend.database import DBSessionMixin
from src.util.logging import Logger
import os
import re
from typing import List, Dict
from src.models.base import Asset
from sqlalchemy import select
import asyncio


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
        Job.__init__(self, job_type=JobType.INDEXER)
        DBSessionMixin.__init__(self)
        self.logger = Logger("FileSearchJob")
        self.regex_pattern = regex_pattern

    def _should_skip_file(self, file_path: str) -> bool:
        """Check if we should skip this file"""
        _, ext = os.path.splitext(file_path.lower())
        return ext in self.SKIP_EXTENSIONS

    def _search_file(self, file_path: str, pattern: re.Pattern) -> List[Dict]:
        """Search a single file for regex matches"""
        try:
            # Skip binary and known binary extensions
            if self._should_skip_file(file_path) or is_binary_file(file_path):
                return []

            # Read file content
            with open(file_path, "r") as f:
                content = f.read()

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
            self.status = JobStatus.RUNNING
            results = []

            # Get all assets with local paths from database
            with self.get_session() as session:
                stmt = select(Asset).where(Asset.local_path.isnot(None))
                assets = session.execute(stmt).scalars().all()
                path_to_asset = {asset.local_path: asset for asset in assets}

            # Compile regex pattern
            pattern = re.compile(self.regex_pattern)

            # Search through assets
            for local_path, asset in path_to_asset.items():
                if not os.path.exists(local_path):
                    continue

                try:
                    # Handle both files and directories
                    if os.path.isfile(local_path):
                        file_matches = await self._search_file_async(local_path, pattern)
                        if file_matches:
                            results.append(
                                {
                                    "asset": {
                                        "id": asset.id,
                                        "asset_type": asset.asset_type,
                                        "source_url": asset.source_url,
                                        "local_path": local_path,
                                        "extra_data": asset.extra_data,
                                    },
                                    "matches": file_matches,
                                }
                            )
                    else:  # Directory
                        dir_matches = await self._search_directory_async(local_path, pattern)
                        if dir_matches:
                            # Flatten directory matches
                            all_matches = []
                            for dir_match in dir_matches:
                                all_matches.extend(dir_match["matches"])

                            if all_matches:
                                results.append(
                                    {
                                        "asset": {
                                            "id": asset.id,
                                            "asset_type": asset.asset_type,
                                            "source_url": asset.source_url,
                                            "local_path": local_path,
                                            "extra_data": asset.extra_data,
                                        },
                                        "matches": all_matches,
                                    }
                                )

                except Exception as e:
                    self.logger.error(f"Error processing asset {local_path}: {str(e)}")
                    continue

            # Format results for output
            formatted_results = []
            for result in results:
                asset = result["asset"]
                for match in result["matches"]:
                    formatted_results.append(
                        {
                            "asset_id": asset["id"],
                            "asset_type": asset["asset_type"],
                            "source_url": asset["source_url"],
                            "local_path": asset["local_path"],
                            "match": match["match"],
                            "context": match["context"],
                            "start": match["start"],
                            "end": match["end"],
                        }
                    )

            # Create result with outputs
            self.result = JobResult(success=True, message=f"Found matches in {len(results)} assets", data={"results": results})

            # Add formatted outputs
            for match in formatted_results:
                output = (
                    f"Match in {match['asset_id']} ({match['asset_type']}):\n"
                    f"Source: {match['source_url']}\n"
                    f"File: {match['local_path']}\n"
                    f"Match: {match['match']}\n"
                    f"Context: {match['context']}\n"
                )
                self.result.add_output(output)

            # Set final status
            self.status = JobStatus.COMPLETED

        except Exception as e:
            self.logger.error(f"Error in file search: {str(e)}")
            self.status = JobStatus.FAILED
            self.error = str(e)
            raise

    async def stop(self) -> None:
        """Stop the job - nothing to do for search"""
