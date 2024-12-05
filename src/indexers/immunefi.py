from abc import ABC, abstractmethod
from typing import Dict
import aiohttp
import json
from src.models.base import Project, Asset, AssetType
from datetime import datetime
from src.backend.database import DBSessionMixin
from src.config.config import Config
from src.util.etherscan import fetch_verified_sources
from urllib.parse import urlparse
import os
import aiofiles
from src.util.github import fetch_github_file, fetch_github_repo
import shutil
from src.util.logging import Logger
from src.handlers.base import HandlerTrigger
from src.handlers.registry import HandlerRegistry
import threading
from sqlalchemy.orm import Session

class ImmunefiIndexer:
    """Immunefi indexer implementation"""
    
    def __init__(self, session: Session, initialize_mode: bool = False):
        self.logger = Logger("ImmunefiIndexer")
        self.session = session
        self.initialize_mode = initialize_mode
        self.config = Config()
        self._stop_event = threading.Event()
        self.handler_registry = None if initialize_mode else HandlerRegistry()

    def stop(self):
        """Signal the indexer to stop"""
        self._stop_event.set()

    async def index(self):
        """Fetch and index bounties"""
        try:
            url = self.config.get('api', {}).get('immunefi', {}).get('url',
                "https://immunefi.com/public-api/bounties.json")
                
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    bounty_data = await response.json()
            
            # Track current project names
            current_projects = {project['project'] for project in bounty_data if 'project' in project}
            
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
            projects = self.session.query(Project).filter(
                Project.project_type == "immunefi"
            ).all()
            
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
                                
                        # Trigger event for asset removal if not in initialize mode
                        if not self.initialize_mode and self.handler_registry:
                            self.handler_registry.trigger_event(
                                HandlerTrigger.ASSET_UPDATED,
                                {
                                    'asset': asset,
                                    'old_revision': asset.extra_data.get('revision'),
                                    'new_revision': None,
                                    'removed': True
                                }
                            )
                    
                    # Delete project from database
                    self.session.delete(project)
                    
                    # Trigger event for project removal if not in initialize mode
                    if not self.initialize_mode and self.handler_registry:
                        self.handler_registry.trigger_event(
                            HandlerTrigger.PROJECT_UPDATED,
                            {
                                'project': project,
                                'removed': True
                            }
                        )
            
            self.session.commit()
            
        except Exception as e:
            self.logger.error(f"Error cleaning up removed projects: {str(e)}")
            self.session.rollback()

    async def process_bounty(self, bounty_data):
        """Process and store bounty data as a Project."""
        existing_project = self.session.query(Project).filter(
            Project.name == bounty_data['project'],
            Project.project_type == "immunefi"
        ).first()
        
        # Get current asset URLs from bounty data
        current_asset_urls = {asset['url'] for asset in bounty_data.get('assets', []) if asset.get('url')}
        
        if not existing_project:
            # Collect all keywords from various fields
            keywords = set()
            
            # Add ecosystem items
            if bounty_data.get('ecosystem'):
                keywords.update(bounty_data['ecosystem'])
                
            # Add product types
            if bounty_data.get('productType'):
                keywords.update(bounty_data['productType'])
                
            # Add program types
            if bounty_data.get('programType'):
                keywords.update(bounty_data['programType'])
                
            # Add project types
            if bounty_data.get('projectType'):
                keywords.update(bounty_data['projectType'])
                
            # Add languages
            if bounty_data.get('language'):
                keywords.update(bounty_data['language'])
                
            # Add features
            if bounty_data.get('features'):
                keywords.update(bounty_data['features'])
            
            new_project = Project(
                name=bounty_data['project'],
                description=bounty_data['description'],
                project_type="immunefi",
                keywords=list(keywords),  # Convert set to list for JSON storage
                extra_data={
                    'assets': bounty_data.get('assets', []),
                    'launchDate': bounty_data.get('launchDate'),
                    'updatedDate': bounty_data.get('updatedDate')
                }
            )
            
            try:
                self.session.add(new_project)
                self.session.commit()
                
                # Process assets after successful project commit
                asset_data = bounty_data.get('assets', [])
                await self.download_assets(new_project.id, asset_data)
                
                # Only trigger events if not in initialize mode
                if not self.initialize_mode and self.handler_registry:
                    self.handler_registry.trigger_event(
                        HandlerTrigger.NEW_PROJECT,
                        {'project': new_project}
                    )
            except Exception as e:
                self.logger.error(f"Error processing project {new_project.id}: {e}")
                self.session.rollback()
                raise
        else:
            # Download assets for existing project
            await self.download_assets(existing_project.id, bounty_data.get('assets', []))
            
            # Clean up out-of-scope assets
            await self.cleanup_removed_assets(existing_project, current_asset_urls)

    async def cleanup_removed_assets(self, project: Project, current_asset_urls: set):
        """Remove assets that are no longer in project scope"""
        try:
            # Get all assets currently associated with the project
            for asset in project.assets:
                if asset.id not in current_asset_urls:
                    self.logger.info(f"Asset {asset.id} no longer in scope for project {project.name}, removing")
                    
                    # Delete local files if they exist
                    if asset.local_path and os.path.exists(asset.local_path):
                        if os.path.isdir(asset.local_path):
                            await self._remove_dir(asset.local_path)
                        else:
                            await self._remove_file(asset.local_path)
                    
                    # Remove asset from project's assets
                    project.assets.remove(asset)
                    
                    # Delete asset from database
                    self.session.delete(asset)
                    
                    # Trigger event if not in initialize mode
                    if not self.initialize_mode and self.handler_registry:
                        self.handler_registry.trigger_event(
                            HandlerTrigger.ASSET_UPDATED,
                            {
                                'asset': asset,
                                'old_revision': asset.extra_data.get('revision'),
                                'new_revision': None,
                                'removed': True
                            }
                        )
            
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

    async def download_assets(self, project_id: str, asset_data):
        """Download asset files and create Asset records."""
        if not asset_data:
            return

        base_dir = os.path.join(self.config.data_dir, str(project_id))
        os.makedirs(base_dir, exist_ok=True)

        for asset in asset_data:
            url = asset.get('url')
            revision = asset.get('revision')
            if not url:
                continue

            self.logger.info(f"Processing {url}")

            try:
                parsed_url = urlparse(url)
                target_dir = os.path.join(base_dir, parsed_url.netloc, parsed_url.path.strip('/'))

                # Check if asset already exists
                existing_asset = self.session.query(Asset).filter(Asset.id == url).first()

                # If asset exists, check if we need to update based on revision
                if existing_asset:
                    existing_revision = existing_asset.extra_data.get('revision')
                    if existing_revision == revision:
                        self.logger.info(f"Skipping {url} - revision {revision} already downloaded")
                        continue
                    elif existing_revision and revision and existing_revision > revision:
                        self.logger.info(f"Skipping {url} - existing revision {existing_revision} is newer than {revision}")
                        continue
                    
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
                    asset_record = Asset(id=url)

                # Update asset metadata
                asset_record.extra_data = asset_record.extra_data or {}
                asset_record.extra_data['revision'] = revision
                asset_record.source_url = url

                # Download based on URL type
                if 'github.com' in parsed_url.netloc:
                    if '/blob/' in url:
                        asset_type = AssetType.GITHUB_FILE
                        await fetch_github_file(url, target_dir)
                        asset_record.asset_type = asset_type
                        asset_record.local_path = target_dir
                        asset_record.extra_data['file_url'] = url
                    else:
                        asset_type = AssetType.GITHUB_REPO
                        await fetch_github_repo(url, target_dir)
                        asset_record.asset_type = asset_type
                        asset_record.local_path = target_dir
                        asset_record.extra_data['repo_url'] = url
                elif 'etherscan.io' in url:
                    try:
                        asset_type = AssetType.DEPLOYED_CONTRACT
                        await fetch_verified_sources(url, target_dir)
                        asset_record.asset_type = asset_type
                        asset_record.local_path = target_dir
                        asset_record.extra_data['explorer_url'] = url
                    except Exception as e:
                        self.logger.warning(f"Failed to fetch Etherscan contract at {url}: {str(e)}")
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
                    if existing_asset:
                        old_revision = existing_asset.extra_data.get('revision')
                        if old_revision != revision:
                            self.handler_registry.trigger_event(
                                HandlerTrigger.ASSET_UPDATED,
                                {
                                    'asset': asset_record,
                                    'old_revision': old_revision,
                                    'new_revision': revision
                                }
                            )
                    else:
                        self.handler_registry.trigger_event(
                            HandlerTrigger.NEW_ASSET,
                            {'asset': asset_record}
                        )

                self.session.commit()

            except Exception as e:
                self.logger.warning(f"Error in asset processing loop for {url}: {str(e)}")
                continue

