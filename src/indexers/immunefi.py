import aiohttp
from src.models.base import Project, Asset, AssetType
from src.config.config import Config
from src.util.etherscan import fetch_verified_sources
from urllib.parse import urlparse
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
            self.logger.info(f"Current asset URLs: {current_asset_urls}")

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

                    # Delete local files if they exist
                    if asset.local_path and os.path.exists(asset.local_path):
                        if os.path.isdir(asset.local_path):
                            await self._remove_dir(asset.local_path)
                        else:
                            await self._remove_file(asset.local_path)

                    # Trigger event if not in initialize mode
                    await self.trigger_event(HandlerTrigger.ASSET_REMOVE, {"asset": asset, "project": project})

                    # Delete asset from database
                    self.session.delete(asset)

            self.session.commit()

        except Exception as e:
            self.logger.error(f"Error cleaning up removed assets for project {project.name}: {str(e)}")
            self.session.rollback()

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

        self.logger.info(f"Download assets called with handler_registry: {self.handler_registry}")
        self.logger.info(f"Initialize mode: {self.initialize_mode}")

        base_dir = os.path.join(self.config.data_dir, str(project_id))
        os.makedirs(base_dir, exist_ok=True)

        for asset in asset_data:
            url = asset.get("url")
            revision = asset.get("revision")
            if not url:
                continue

            self.logger.info(f"Processing {url} with revision {revision}")

            try:
                parsed_url = urlparse(url)
                target_dir = os.path.join(base_dir, parsed_url.netloc, parsed_url.path.strip("/"))

                # Check if asset already exists using identifier field
                existing_asset = self.session.query(Asset).filter(Asset.identifier == url).first()

                # If asset exists, check if we need to update based on revision
                if existing_asset:
                    existing_revision = existing_asset.extra_data.get("revision")
                    if existing_revision == revision:
                        self.logger.info(f"Skipping {url} - revision {revision} already downloaded")
                        continue
                    elif existing_revision and revision and existing_revision > revision:
                        self.logger.info(f"Skipping {url} - existing revision {existing_revision} is newer than {revision}")
                        continue

                    # Store old revision before updating
                    old_revision = existing_revision

                    # For files that we want to diff, preserve the old content
                    old_path = None
                    if existing_asset.asset_type == AssetType.GITHUB_FILE.value and existing_asset.local_path:
                        self.logger.info("Creating backup of old file")
                        # Create backup of old file
                        old_path = f"{existing_asset.local_path}.old"
                        if os.path.exists(existing_asset.local_path):
                            await asyncio.to_thread(shutil.copy2, existing_asset.local_path, old_path)

                    # Delete old files before downloading new version
                    if existing_asset.local_path and os.path.exists(existing_asset.local_path):
                        self.logger.info(f"Deleting old version at {existing_asset.local_path}")
                        if os.path.isdir(existing_asset.local_path):
                            await self._remove_dir(existing_asset.local_path)
                        else:
                            await self._remove_file(existing_asset.local_path)

                    # Update the existing asset record
                    asset_record = existing_asset
                else:
                    # Create a new asset record
                    asset_record = Asset(identifier=url, project_id=project_id)  # Set project_id directly

                # Update asset metadata
                asset_record.extra_data = asset_record.extra_data or {}
                asset_record.extra_data["revision"] = revision
                asset_record.source_url = url

                # Download based on URL type
                if "github.com" in parsed_url.netloc:
                    if "/blob/" in url:
                        asset_type = AssetType.GITHUB_FILE
                        await fetch_github_file(url, target_dir)
                        asset_record.asset_type = asset_type
                        asset_record.local_path = target_dir
                        asset_record.extra_data["file_url"] = url
                    else:
                        asset_type = AssetType.GITHUB_REPO
                        await fetch_github_repo(url, target_dir)
                        asset_record.asset_type = asset_type
                        asset_record.local_path = target_dir
                        asset_record.extra_data["repo_url"] = url
                elif "etherscan.io" in url:
                    try:
                        asset_type = AssetType.DEPLOYED_CONTRACT
                        await fetch_verified_sources(url, target_dir)
                        asset_record.asset_type = asset_type
                        asset_record.local_path = target_dir
                        asset_record.extra_data["explorer_url"] = url
                    except Exception as e:
                        self.logger.warning(f"Failed to fetch Etherscan contract at {url}: {str(e)}")
                        continue
                else:
                    # Check if it's a supported EVM explorer
                    from src.util.etherscan import EVMExplorer

                    explorer = EVMExplorer()
                    is_supported, explorer_type = explorer.is_supported_explorer(url)

                    if is_supported:
                        try:
                            asset_type = AssetType.DEPLOYED_CONTRACT
                            await fetch_verified_sources(url, target_dir)
                            asset_record.asset_type = asset_type
                            asset_record.local_path = target_dir
                            asset_record.extra_data["explorer_url"] = url
                        except Exception as e:
                            self.logger.warning(f"Failed to fetch contract from {explorer_type.value} at {url}: {str(e)}")
                            continue
                    else:
                        self.logger.warning(f"Unsupported asset URL: {url}")
                        continue

                # Associate the asset with the project if it's new
                if not existing_asset:
                    project = self.session.query(Project).filter(Project.id == project_id).first()
                    if project:
                        project.assets.append(asset_record)
                        self.session.add(asset_record)

                # Only handle events if not in initialize mode
                if not self.initialize_mode:
                    self.logger.info("Not in initialize mode, handling events")
                    if existing_asset:
                        self.logger.info(f"Checking revision update - old: {old_revision}, new: {revision}")
                        if old_revision != revision:
                            self.logger.info("Revision changed, triggering update event")
                            event_data = {"asset": asset_record, "old_revision": old_revision, "new_revision": revision}

                            # Add diff data for files
                            if old_path and os.path.exists(old_path):
                                event_data["old_path"] = old_path
                                event_data["new_path"] = target_dir

                            self.logger.info(f"Triggering ASSET_UPDATE event with data: {event_data}")
                            await self.trigger_event(HandlerTrigger.ASSET_UPDATE, event_data)

                            # Clean up old file after event is triggered
                            if old_path and os.path.exists(old_path):
                                await self._remove_file(old_path)
                    else:
                        self.logger.info("Triggering NEW_ASSET event")
                        await self.trigger_event(HandlerTrigger.NEW_ASSET, {"asset": asset_record})

                self.session.commit()

            except Exception as e:
                self.logger.warning(f"Error in asset processing loop for {url}: {str(e)}")
                continue
