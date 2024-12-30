import aiohttp
from src.models.base import Project, Asset, AssetType
from src.config.config import Config
from src.util.etherscan import fetch_verified_sources
import os
import asyncio
from src.util.github import fetch_github_file, fetch_github_repo
import shutil
from src.util.logging import Logger
from src.handlers.base import HandlerTrigger
from src.handlers.registry import HandlerRegistry
import threading
from sqlalchemy.orm import Session
from datetime import datetime
from src.backend.asset_storage import AssetStorage
from sqlalchemy import text


def _serialize_datetime(obj):
    """Convert datetime objects to ISO format strings."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def _serialize_model(model, depth=0):
    """Safely serialize a SQLAlchemy model to a dictionary."""
    if not model or depth > 1:  # Limit recursion depth
        return None

    # Define safe attributes to serialize for each model type
    safe_attrs = {
        Project: ["id", "name", "description", "project_type", "project_source", "keywords", "extra_data"],
        Asset: ["id", "asset_type", "local_path", "source_url", "extra_data"],
    }

    model_type = type(model)
    if model_type not in safe_attrs:
        return str(model)

    data = {}
    for attr in safe_attrs[model_type]:
        value = getattr(model, attr, None)
        if isinstance(value, datetime):
            data[attr] = value.isoformat()
        elif isinstance(value, (list, set)):
            if value and isinstance(next(iter(value)), (Project, Asset)):
                if depth < 1:  # Only serialize nested models at depth 0
                    data[attr] = [_serialize_model(item, depth + 1) for item in value]
                else:
                    data[attr] = [item.id for item in value]  # Just include IDs at deeper levels
            else:
                data[attr] = list(value)
        elif isinstance(value, (Project, Asset)):
            if depth < 1:  # Only serialize nested models at depth 0
                data[attr] = _serialize_model(value, depth + 1)
            else:
                data[attr] = value.id  # Just include ID at deeper levels
        else:
            data[attr] = value
    return data


def _serialize_event_data(event_data):
    """Safely serialize event data."""
    if not isinstance(event_data, dict):
        return event_data

    result = {}
    for key, value in event_data.items():
        if isinstance(value, (Project, Asset)):
            result[key] = _serialize_model(value)
        elif isinstance(value, dict):
            result[key] = _serialize_event_data(value)
        elif isinstance(value, list):
            result[key] = [_serialize_event_data(item) for item in value]
        else:
            result[key] = _serialize_datetime(value)
    return result


class ImmunefiIndexer:
    """Immunefi indexer implementation"""

    def __init__(self, session: Session, initialize_mode: bool = False):
        self.logger = Logger("ImmunefiIndexer")
        self.session = session
        self.initialize_mode = initialize_mode
        self.config = Config()
        self._stop_event = threading.Event()
        self.handler_registry = None if initialize_mode else HandlerRegistry()

    async def trigger_event(self, event_type: HandlerTrigger, event_data: dict):
        """Safely trigger an event with serialized data."""
        if not self.initialize_mode and self.handler_registry:
            # Skip serialization for asset events that need model objects
            if event_type in [HandlerTrigger.NEW_ASSET, HandlerTrigger.ASSET_UPDATE]:
                await self.handler_registry.trigger_event(event_type, event_data)
            else:
                # Serialize data for other events
                serialized_data = _serialize_event_data(event_data)
                await self.handler_registry.trigger_event(event_type, serialized_data)

    def stop(self):
        """Signal the indexer to stop"""
        self._stop_event.set()

    async def index(self):
        """Fetch and index bounties"""
        try:
            url = self.config.get("api", {}).get("immunefi", {}).get("url", "https://immunefi.com/public-api/bounties.json")

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    bounty_data = await response.json()

            # Normalize asset revisions - keep only latest revision for each asset
            asset_revisions = {}  # url -> latest revision
            for project in bounty_data:
                for asset in project.get("assets", []):
                    url = asset.get("url")
                    revision = asset.get("revision")
                    if url and revision is not None:
                        if url not in asset_revisions or revision > asset_revisions[url]:
                            asset_revisions[url] = revision
                            self.logger.debug(f"Found revision {revision} for {url}")

            # Update bounty data with normalized revisions
            for project in bounty_data:
                if "assets" in project:
                    project["assets"] = [
                        {**asset, "revision": asset_revisions.get(asset["url"], asset.get("revision"))}
                        for asset in project["assets"]
                        if asset.get("url") in asset_revisions
                    ]

            # Track current project names
            current_projects = {project["project"] for project in bounty_data if "project" in project}

            # Process all current projects
            for project_data in bounty_data:
                if self._stop_event.is_set():
                    self.logger.info("Indexing stopped by request")
                    break

                await self.process_bounty(project_data)

            # Clean up removed projects
            await self.cleanup_removed_projects(current_projects)

        except Exception as e:
            self.logger.error(f"Failed to index Immunefi: {str(e)}")
            raise

    async def cleanup_removed_projects(self, current_projects: set):
        """Remove projects that are no longer listed in Immunefi"""
        try:
            # Get all Immunefi projects from database
            projects = (
                self.session.query(Project)
                .filter(Project.project_type == "bounty", Project.project_source == "immunefi")
                .all()
            )

            # Update any old projects that might not have project_source set
            old_projects = self.session.query(Project).filter(Project.project_type == "immunefi").all()

            if old_projects:
                self.logger.info(f"Found {len(old_projects)} projects to update with new fields")
                for project in old_projects:
                    project.project_type = "bounty"
                    project.project_source = "immunefi"
                self.session.commit()

            for project in projects:
                if project.name not in current_projects:
                    self.logger.info(f"Project {project.name} no longer listed in Immunefi, removing")

                    # Clean up all associated assets first
                    for asset in project.assets:
                        # Delete local files if they exist
                        if asset.local_path and os.path.exists(asset.local_path):
                            if os.path.isdir(asset.local_path):
                                await self._remove_dir(asset.local_path)
                            else:
                                await self._remove_file(asset.local_path)

                        # Trigger event for asset removal
                        await self.trigger_event(HandlerTrigger.ASSET_REMOVE, {"asset": asset, "project": project})

                        # Delete asset from database
                        self.session.delete(asset)

                    # Trigger project removal event
                    await self.trigger_event(HandlerTrigger.PROJECT_REMOVE, {"project": project, "removed": True})

                    # Delete project from database
                    self.session.delete(project)

            self.session.commit()

        except Exception as e:
            self.logger.error(f"Error cleaning up removed projects: {str(e)}")
            self.session.rollback()
            raise

    async def process_bounty(self, bounty_data: dict) -> None:
        """Process a single bounty program"""
        try:
            self.logger.info(f"Processing bounty: {bounty_data['project']}")

            existing_project = (
                self.session.query(Project)
                .filter(
                    Project.name == bounty_data["project"],
                    Project.project_type == "bounty",
                    Project.project_source == "immunefi",
                )
                .first()
            )

            # Get current asset URLs from bounty data
            current_asset_urls = {asset["url"] for asset in bounty_data.get("assets", []) if asset.get("url")}
            self.logger.debug(f"Current asset URLs: {current_asset_urls}")

            # Collect all keywords from various fields
            keywords = set()

            # Add ecosystem items
            if bounty_data.get("ecosystem"):
                keywords.update(bounty_data["ecosystem"])

            # Add product types
            if bounty_data.get("productType"):
                keywords.update(bounty_data["productType"])

            # Add program types
            if bounty_data.get("programType"):
                keywords.update(bounty_data["programType"])

            # Add project types
            if bounty_data.get("projectType"):
                keywords.update(bounty_data["projectType"])

            # Add languages
            if bounty_data.get("language"):
                keywords.update(bounty_data["language"])

            # Add features
            if bounty_data.get("features"):
                keywords.update(bounty_data["features"])

            # Prepare extra data with serialized dates
            extra_data = _serialize_event_data(
                {
                    "launchDate": bounty_data.get("launchDate"),
                    "updatedDate": bounty_data.get("updatedDate"),
                    "maxBounty": bounty_data.get("maxBounty"),
                    "ecosystem": bounty_data.get("ecosystem"),
                    "productType": bounty_data.get("productType"),
                    "programType": bounty_data.get("programType"),
                    "projectType": bounty_data.get("projectType"),
                    "language": bounty_data.get("language"),
                    "features": bounty_data.get("features"),
                }
            )

            if not existing_project:
                self.logger.info("Creating new project")
                new_project = Project(
                    name=bounty_data["project"],
                    description=bounty_data.get("description", ""),
                    project_type="bounty",
                    project_source="immunefi",
                    keywords=list(keywords),  # Convert set to list for JSON storage
                    extra_data=extra_data,
                )

                try:
                    self.session.add(new_project)
                    self.session.commit()

                    # Process assets after successful project commit
                    asset_data = bounty_data.get("assets", [])
                    await self.download_assets(new_project.id, asset_data)

                    # Only trigger events if not in initialize mode
                    await self.trigger_event(HandlerTrigger.NEW_PROJECT, {"project": new_project})

                except Exception as e:
                    self.logger.error(f"Error processing project {new_project.id}: {e}")
                    self.session.rollback()
                    raise
            else:
                self.logger.info(f"Found existing project: {existing_project.name}")

                # Store old project state for comparison
                old_project = Project(
                    name=existing_project.name,
                    description=existing_project.description,
                    project_type=existing_project.project_type,
                    project_source=existing_project.project_source,
                    keywords=existing_project.keywords.copy() if existing_project.keywords else [],
                    extra_data=existing_project.extra_data.copy() if existing_project.extra_data else {},
                    assets=existing_project.assets.copy() if existing_project.assets else [],
                )

                # Check for changes
                has_changes = False

                # Update basic fields
                if existing_project.description != bounty_data.get("description", ""):
                    existing_project.description = bounty_data.get("description", "")
                    has_changes = True

                # Update keywords
                if set(existing_project.keywords or []) != keywords:
                    existing_project.keywords = list(keywords)
                    has_changes = True

                # Update extra data
                if existing_project.extra_data != extra_data:
                    existing_project.extra_data = extra_data
                    has_changes = True

                # Download assets for existing project
                await self.download_assets(existing_project.id, bounty_data.get("assets", []))

                # Clean up out-of-scope assets
                await self.cleanup_removed_assets(existing_project, current_asset_urls)

                # Commit changes
                self.session.commit()

                # Trigger update event if there were changes and not in initialize mode
                if has_changes:
                    await self.trigger_event(
                        HandlerTrigger.PROJECT_UPDATE, {"project": existing_project, "old_project": old_project}
                    )

        except Exception as e:
            self.logger.error(f"Error processing project {bounty_data.get('project', 'unknown')}: {str(e)}")
            raise

    async def cleanup_removed_assets(self, project: Project, current_asset_urls: set):
        """Remove assets that are no longer in project scope"""
        try:
            # Get all assets currently associated with the project
            for asset in project.assets:
                if asset.identifier not in current_asset_urls:
                    self.logger.info(f"Asset {asset.identifier} no longer in scope for project {project.name}, removing")

                    # Trigger event BEFORE deletion if not in initialize mode
                    if not self.initialize_mode:
                        await self.trigger_event(HandlerTrigger.ASSET_REMOVE, {"asset": asset, "project": project})

                    # Delete local files if they exist
                    if asset.local_path and os.path.exists(asset.local_path):
                        if os.path.isdir(asset.local_path):
                            await self._remove_dir(asset.local_path)
                        else:
                            await self._remove_file(asset.local_path)

                    # Delete asset from database
                    self.session.delete(asset)

            self.session.commit()

        except Exception as e:
            self.logger.error(f"Error cleaning up removed assets for project {project.name}: {str(e)}")
            self.session.rollback()
            raise  # Re-raise the exception to handle it in the caller

    async def _remove_dir(self, path: str):
        """Asynchronously remove a directory"""
        await asyncio.to_thread(shutil.rmtree, path)

    async def _remove_file(self, path: str):
        """Asynchronously remove a file"""
        await asyncio.to_thread(os.remove, path)

    async def download_assets(self, project_id: int, asset_data):
        """Download asset files and create Asset records."""
        if not asset_data:
            return

        base_dir = os.path.join(self.config.data_dir, str(project_id))
        os.makedirs(base_dir, exist_ok=True)

        for asset in asset_data:
            url = asset.get("url")
            revision = asset.get("revision")

            if not url:
                continue

            self.logger.debug(f"Processing {url} with revision {revision}")

            try:
                # Find existing asset
                existing_asset = self.session.query(Asset).filter(Asset.identifier == url).first()

                if existing_asset:
                    # Debug logging for revision check
                    self.logger.debug(f"Found existing asset: {existing_asset.id}")
                    self.logger.debug(f"Current extra_data: {existing_asset.extra_data}")
                    self.logger.debug(
                        f"Current revision in DB: {existing_asset.extra_data.get('revision') if existing_asset.extra_data else None}"
                    )
                    self.logger.debug(f"New revision from API: {revision}")

                    # Check if anything has actually changed
                    if existing_asset.extra_data and existing_asset.extra_data.get("revision") == revision:
                        self.logger.debug(f"Asset {url} already exists with same revision")
                        continue

                    # Get old code BEFORE any changes or cleanup
                    old_code = None
                    new_code = None
                    can_diff = existing_asset.asset_type in [AssetType.GITHUB_FILE, AssetType.DEPLOYED_CONTRACT]
                    old_revision = existing_asset.extra_data.get("revision") if existing_asset.extra_data else None

                    self.logger.debug(f"Asset type before getting old code: {existing_asset.asset_type}")
                    if can_diff:
                        try:
                            old_code = existing_asset.get_code()
                            self.logger.debug(f"Successfully got old code, length: {len(old_code) if old_code else 0}")
                        except Exception as e:
                            self.logger.error(f"Failed to get old code: {e}")

                    # Create new directory path
                    target_dir, _ = AssetStorage.get_asset_path(base_dir, url)

                    # Store old code before cleaning up
                    old_code_backup = old_code

                    # Now it's safe to clean up old files
                    if os.path.exists(target_dir):
                        self.logger.info(f"Cleaning up old path: {target_dir}")
                        try:
                            if os.path.isfile(target_dir):
                                await self._remove_file(target_dir)
                                # Ensure parent directory exists
                                os.makedirs(os.path.dirname(target_dir), exist_ok=True)
                            else:
                                for item in os.listdir(target_dir):
                                    item_path = os.path.join(target_dir, item)
                                    if os.path.isfile(item_path):
                                        await self._remove_file(item_path)
                                    elif os.path.isdir(item_path):
                                        await self._remove_dir(item_path)
                        except Exception as e:
                            self.logger.error(f"Error during cleanup: {e}")

                    # Update existing asset
                    if "github.com" in url:
                        if "/blob/" in url:
                            existing_asset.asset_type = AssetType.GITHUB_FILE
                            await fetch_github_file(url, target_dir)
                        else:
                            existing_asset.asset_type = AssetType.GITHUB_REPO
                            await fetch_github_repo(url, target_dir)
                    elif any(explorer in url for explorer in ["etherscan.io", "bscscan.com", "polygonscan.com"]):
                        existing_asset.asset_type = AssetType.DEPLOYED_CONTRACT
                        await fetch_verified_sources(url, target_dir)

                    # Update metadata
                    existing_asset.extra_data = existing_asset.extra_data or {}
                    existing_asset.extra_data["revision"] = revision
                    existing_asset.source_url = url
                    existing_asset.local_path = target_dir

                    # Get new code AFTER downloading
                    self.logger.info(f"Asset type before getting new code: {existing_asset.asset_type}")
                    if can_diff:
                        try:
                            new_code = existing_asset.get_code()
                            self.logger.info(f"Successfully got new code, length: {len(new_code) if new_code else 0}")
                        except Exception as e:
                            self.logger.error(f"Failed to get new code: {e}")

                    if not self.initialize_mode:
                        self.logger.info(f"Asset changed - old revision: {old_revision}, new revision: {revision}")

                        # Create event data
                        event_data = {
                            "asset": existing_asset,
                            "old_revision": old_revision,
                            "new_revision": revision,
                            "old_path": target_dir,
                            "new_path": target_dir,
                        }

                        if can_diff and old_code_backup is not None and new_code is not None:
                            event_data["old_code"] = old_code_backup
                            event_data["new_code"] = new_code
                            self.logger.debug("Added code to event data for diffing")

                        # Trigger the event
                        await self.trigger_event(HandlerTrigger.ASSET_UPDATE, event_data)

                        # Update the asset's revision using raw SQL
                        self.logger.info(f"Updating asset {existing_asset.id} revision to {revision}")

                        # Debug the session type
                        self.logger.info(f"Session type: {type(self.session)}")

                        update_sql = text(
                            """
                        UPDATE assets
                        SET extra_data = CAST(extra_data AS jsonb) || jsonb_build_object('revision', CAST(:revision AS integer))
                        WHERE id = :asset_id
                        RETURNING id, extra_data;
                        """
                        )

                        try:
                            # Execute with RETURNING to see what happened
                            result = self.session.execute(
                                update_sql, {"revision": revision, "asset_id": existing_asset.id}  # Keep as integer
                            )

                            # Log the result
                            updated = result.first()
                            self.logger.info(f"Update result: {updated}")

                            # Explicitly commit
                            self.session.commit()
                            self.logger.info("Commit completed")

                            # Double check with a separate query
                            verify_sql = text("SELECT id, extra_data FROM assets WHERE id = :asset_id")
                            verify_result = self.session.execute(verify_sql, {"asset_id": existing_asset.id})
                            verify_row = verify_result.first()
                            self.logger.info(f"Verification query result: {verify_row}")

                        except Exception as e:
                            self.logger.error(f"Error during update: {str(e)}")
                            self.logger.error(f"Error type: {type(e)}")
                            self.session.rollback()
                            raise

                        # Expire all objects to force reload from DB
                        self.session.expire_all()

                    # Final commit to ensure all changes are saved
                    if hasattr(self.session, "commit"):
                        self.session.commit()
                    else:
                        await self.session.commit()

                self.session.commit()

            except Exception as e:
                self.logger.warning(f"Error in asset processing loop for {url}: {str(e)}")
                self.session.rollback()
                continue
