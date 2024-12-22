import os
from typing import List
from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.actions.result import ActionResult
from src.util.logging import Logger
from src.models.base import Asset, AssetType
from src.backend.database import DBSessionMixin


class GetCodeAction(BaseAction):
    """Action to get code contents for an asset"""

    spec = ActionSpec(
        name="get_code",
        description="Get code contents for a specific asset",
        help_text="""Get the code contents for a specific asset by ID.

Usage:
/get_code <asset-id>

Arguments:
- asset-id: ID of the asset to get code from

Supported asset types:
- GITHUB_FILE: Returns the contents of the file
- DEPLOYED_CONTRACT: Returns concatenated contents of all files in the contract directory
- GITHUB_REPO: Not supported (will return error)

Examples:
/get_code 123     # Get code for asset with ID 123""",
        agent_hint="Use this command to retrieve the actual code contents of a specific file or contract",
        arguments=[
            ActionArgument(name="asset_id", description="ID of the asset to get code from", required=True),
        ],
    )

    def __init__(self):
        super().__init__()
        self.logger = Logger("GetCodeAction")

    def _read_file_contents(self, path: str) -> str:
        """Read contents of a single file"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            self.logger.error(f"Error reading file {path}: {str(e)}")
            raise

    def _read_directory_contents(self, directory: str) -> str:
        """Read and concatenate contents of all files in directory and subdirectories"""
        contents: List[str] = []

        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    relative_path = os.path.relpath(file_path, directory)
                    file_content = self._read_file_contents(file_path)
                    contents.append(f"// File: {relative_path}\n{file_content}\n")
                except Exception as e:
                    self.logger.error(f"Error reading {file_path}: {str(e)}")
                    continue

        return "\n".join(contents)

    async def execute(self, asset_id: str, **kwargs) -> ActionResult:
        """Execute the get code action"""
        try:
            # Convert asset_id to int
            try:
                asset_id = int(asset_id)
            except ValueError:
                return ActionResult.error("Asset ID must be a number")

            # Get asset from database
            db = DBSessionMixin()
            with db.get_session() as session:
                asset = session.query(Asset).filter(Asset.id == asset_id).first()

                if not asset:
                    return ActionResult.error(f"Asset with ID {asset_id} not found")

                # Check asset type
                if asset.asset_type == AssetType.GITHUB_REPO:
                    return ActionResult.error("Getting code for entire repositories is not supported")

                if not asset.local_path:
                    return ActionResult.error("Asset has no local path")

                if not os.path.exists(asset.local_path):
                    return ActionResult.error("Asset file not found on disk")

                # Get code based on asset type
                if asset.asset_type == AssetType.GITHUB_FILE:
                    code = self._read_file_contents(asset.local_path)
                elif asset.asset_type == AssetType.DEPLOYED_CONTRACT:
                    if not os.path.isdir(asset.local_path):
                        return ActionResult.error("Contract path is not a directory")
                    code = self._read_directory_contents(asset.local_path)
                else:
                    return ActionResult.error(f"Unsupported asset type: {asset.asset_type}")

                return ActionResult.text(code)

        except Exception as e:
            self.logger.error(f"Get code action failed: {str(e)}")
            return ActionResult.error(f"Error getting code: {str(e)}")
