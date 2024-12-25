"""Job to monitor proxy contracts and their implementations"""

from src.jobs.base import Job, JobResult
from src.models.base import Asset, AssetType
from src.backend.database import DBSessionMixin
from src.util.etherscan import EVMExplorer, fetch_verified_sources
from src.handlers.base import HandlerTrigger
from src.handlers.registry import HandlerRegistry
from src.util.logging import Logger
import os
from urllib.parse import urlparse
from src.config.config import Config
import json


class ProxyMonitorJob(Job, DBSessionMixin):
    """Job that monitors proxy contracts for implementation upgrades"""

    def __init__(self):
        super().__init__("proxy_monitor")
        self.logger = Logger("ProxyMonitorJob")
        self.explorer = EVMExplorer()
        self.handler_registry = HandlerRegistry.get_instance()
        self.config = Config()

    async def stop_handler(self) -> None:
        """Handle job stop request - nothing to clean up"""
        return

    async def start(self) -> None:
        """Start the proxy monitoring job"""
        try:
            self.logger.info("Starting proxy contract monitoring")

            with self.get_session() as session:
                # Get contracts that haven't been checked or are known proxies
                contracts = (
                    session.query(Asset)
                    .filter(
                        Asset.asset_type == AssetType.DEPLOYED_CONTRACT,
                        (Asset.checked_for_proxy == False) | (Asset.is_proxy == True),  # noqa: E712
                    )
                    .all()
                )

                self.logger.info(f"Found {len(contracts)} deployed contracts to check")

                for contract in contracts:
                    try:
                        self.logger.info(f"Checking contract {contract.identifier}")

                        # Check for proxy upgrade events
                        events = await self.explorer.get_proxy_upgrade_events(contract.identifier)
                        self.logger.info(f"Got events for {contract.identifier}: {json.dumps(events)}")

                        # Initialize extra_data if None
                        if contract.extra_data is None:
                            contract.extra_data = {}

                        # Update proxy status
                        contract.checked_for_proxy = True
                        contract.is_proxy = bool(events)
                        self.logger.info(f"Set is_proxy={contract.is_proxy} for {contract.identifier}")

                        # Always add and commit the contract after updating proxy status
                        session.add(contract)
                        session.commit()
                        self.logger.info(
                            f"Committed changes for {contract.identifier}: checked_for_proxy={contract.checked_for_proxy}, is_proxy={contract.is_proxy}"
                        )

                        if not events:
                            self.logger.info(f"Marked {contract.identifier} as non-proxy")
                            continue

                        # Get latest implementation address
                        latest_event = events[-1]
                        impl_address = latest_event["implementation"]
                        self.logger.info(f"Latest implementation for {contract.identifier}: {impl_address}")

                        # Get explorer type from contract URL
                        is_supported, explorer_type = self.explorer.is_supported_explorer(contract.identifier)
                        if not is_supported:
                            self.logger.error(f"Unsupported explorer URL: {contract.identifier}")
                            continue

                        # Get explorer domain from config
                        explorer_domain = self.explorer.EXPLORERS[explorer_type]["domain"]
                        impl_url = f"https://{explorer_domain}/address/{impl_address}"
                        self.logger.info(f"Implementation URL: {impl_url}")

                        # Check if implementation changed
                        current_impl = contract.implementation
                        if current_impl and current_impl.identifier == impl_url:
                            self.logger.info(f"Implementation unchanged for {contract.identifier}")
                            continue

                        # Look for existing implementation asset
                        impl_asset = session.query(Asset).filter(Asset.identifier == impl_url).first()
                        self.logger.info(f"Found existing implementation asset: {impl_asset is not None}")

                        # If implementation doesn't exist as an asset yet, create it
                        if not impl_asset:
                            self.logger.info(f"Creating new implementation asset for {impl_url}")
                            # Use same directory structure as immunefi indexer
                            base_dir = os.path.join(self.config.data_dir, str(contract.project_id))
                            parsed_url = urlparse(impl_url)
                            target_dir = os.path.join(base_dir, parsed_url.netloc, parsed_url.path.strip("/"))

                            # Download implementation code
                            self.logger.info(f"Downloading implementation code to {target_dir}")
                            await fetch_verified_sources(impl_url, target_dir)

                            # Create new implementation asset
                            impl_asset = Asset(
                                identifier=impl_url,
                                project_id=contract.project_id,
                                asset_type=AssetType.DEPLOYED_CONTRACT,
                                source_url=impl_url,
                                local_path=target_dir,
                                extra_data={"is_implementation": True, "added_by_proxy_monitor": True},
                            )
                            session.add(impl_asset)
                            self.logger.info(f"Created new implementation asset: {impl_url}")

                        # Update proxy relationship
                        old_impl = contract.implementation
                        contract.implementation = impl_asset
                        self.logger.info(
                            f"Updated implementation for {contract.identifier}: {old_impl.identifier if old_impl else 'None'} -> {impl_asset.identifier}"
                        )

                        # Update implementation history in extra_data
                        if "implementation_history" not in contract.extra_data:
                            contract.extra_data["implementation_history"] = []
                        contract.extra_data["implementation_history"].append(
                            {
                                "address": impl_address,
                                "url": impl_url,
                                "block_number": latest_event["blockNumber"],
                                "timestamp": latest_event["timestamp"],
                            }
                        )
                        self.logger.info(
                            f"Updated implementation history for {contract.identifier}, now has {len(contract.extra_data['implementation_history'])} entries"
                        )

                        # Commit changes
                        session.commit()
                        self.logger.info(f"Committed implementation changes for {contract.identifier}")

                        # Only trigger upgrade event if there was a previous implementation
                        if old_impl:
                            await self.handler_registry.trigger_event(
                                HandlerTrigger.CONTRACT_UPGRADED,
                                {
                                    "proxy": contract,
                                    "old_implementation": old_impl,
                                    "new_implementation": impl_asset,
                                    "event": latest_event,
                                },
                            )

                    except Exception as e:
                        self.logger.error(f"Error processing contract {contract.identifier}: {str(e)}")
                        session.rollback()
                        continue

            await self.complete(JobResult(success=True, message="Proxy monitoring completed successfully"))

        except Exception as e:
            self.logger.error(f"Error in proxy monitoring job: {str(e)}")
            await self.fail(str(e))
