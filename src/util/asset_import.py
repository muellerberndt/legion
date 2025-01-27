import os
import shutil
from src.backend.database import DBSessionMixin
from src.models.base import Asset, Project, AssetType
from src.util.logging import Logger
from src.config.config import Config
from src.backend.asset_storage import AssetStorage


class AssetImporter:
    # File extensions for smart contracts
    SUPPORTED_EXTENSIONS = {
        ".sol",  # Solidity
        ".vy",  # Vyper
    }

    def __init__(self, project_id: int):
        self.project_id = project_id
        self.logger = Logger("AssetImporter")
        self.config = Config()
        self.session_handler = DBSessionMixin()

        # Verify project exists
        with self.session_handler.get_session() as session:
            project = session.query(Project).get(project_id)
            if not project:
                raise ValueError(f"Project with ID {project_id} not found")
            self.project = project

    def import_directory(self, source_dir: str) -> int:
        """
        Import a directory by first copying it entirely, then registering smart contract files
        Returns the number of files imported
        """
        # First, copy the entire directory to the data dir
        target_base = os.path.join(self.config.data_dir, str(self.project_id), "local_imports")
        target_dir = os.path.join(target_base, os.path.basename(source_dir))

        # Ensure target directory exists
        os.makedirs(target_base, exist_ok=True)

        # Copy the entire directory
        self.logger.info(f"Copying directory {source_dir} to {target_dir}")
        shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)

        # Now walk through the copied directory and register supported files
        imported_count = 0
        with self.session_handler.get_session() as session:
            for root, _, files in os.walk(target_dir):
                for file in files:
                    # Skip test files
                    if "test" in file.lower() or ".t." in file.lower():
                        continue

                    # Only process supported files
                    if not any(file.endswith(ext) for ext in self.SUPPORTED_EXTENSIONS):
                        continue

                    try:
                        # Get path relative to the target directory
                        full_path = os.path.join(root, file)
                        relative_path = os.path.relpath(full_path, target_dir)

                        identifier = f"local_file_{self.project_id}_{relative_path}"

                        # Check if asset already exists
                        existing = session.query(Asset).filter(Asset.identifier == identifier).first()
                        if existing:
                            self.logger.debug(f"Asset already exists: {relative_path}")
                            continue

                        # Create new asset
                        asset = Asset(
                            identifier=identifier,
                            project_id=self.project_id,
                            asset_type=AssetType.LOCAL_IMPORT,
                            source_url=None,
                            local_path=full_path,
                            extra_data={"relative_path": relative_path},
                        )

                        session.add(asset)
                        imported_count += 1
                        self.logger.debug(f"Registered: {relative_path}")

                    except Exception as e:
                        self.logger.warning(f"Failed to register {file}: {e}")
                        continue

            session.commit()

        self.logger.info(f"Imported {imported_count} smart contract files")
        return imported_count

    def _is_supported_file(self, filename: str) -> bool:
        """Check if file has a supported extension"""
        return any(filename.lower().endswith(ext) for ext in self.SUPPORTED_EXTENSIONS)

    def _import_file(self, file_path: str):
        """Import a single file as an asset"""
        with self.session_handler.get_session() as session:
            try:
                # Convert to absolute path to handle any relative path inputs
                abs_path = os.path.abspath(file_path)

                # Get path relative to the import directory
                relative_path = os.path.relpath(abs_path, start=os.path.dirname(abs_path))

                identifier = f"local_file_{self.project_id}_{relative_path}"

                # Check if asset already exists
                existing = session.query(Asset).filter(Asset.identifier == identifier).first()
                if existing:
                    self.logger.debug(f"Asset already exists: {relative_path}")
                    return

                # Create target directory in .data folder
                base_dir = os.path.join(self.config.data_dir, str(self.project_id), "local_imports")
                target_dir, relative_path = AssetStorage.get_asset_path(base_dir, relative_path)

                # Construct the full target file path
                target_file = os.path.join(target_dir, os.path.basename(relative_path))

                # Ensure target directory exists
                os.makedirs(target_dir, exist_ok=True)

                # Copy file to target location
                shutil.copy2(abs_path, target_file)

                self.logger.debug(f"Copied {abs_path} to {target_file}")

                # Create new asset
                asset = Asset(
                    identifier=identifier,
                    project_id=self.project_id,
                    asset_type=AssetType.LOCAL_IMPORT,
                    source_url=None,
                    local_path=target_file,  # Store the full target file path
                    extra_data={"original_path": str(abs_path), "relative_path": relative_path},
                )

                session.add(asset)
                session.commit()
                self.logger.debug(f"Imported: {relative_path}")

            except Exception as e:
                self.logger.warning(f"Failed to import {file_path}: {str(e)}")
                raise
