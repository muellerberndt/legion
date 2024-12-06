from src.handlers.base import Handler, HandlerTrigger
from src.services.telegram import TelegramService
from src.util.logging import Logger
from src.backend.database import DBSessionMixin
from src.util.etherscan import EVMExplorer, ExplorerType
from sqlalchemy import text
from typing import Dict, Any, Optional
import json
import traceback
import aiohttp
from extensions.examples.proxy_implementation_upgrade_agent import ProxyImplementationUpgradeAgent

__all__ = ['ProxyImplementationUpgradeHandler']

class ProxyImplementationUpgradeHandler(Handler, DBSessionMixin):
    """Handler for monitoring proxy implementation upgrades"""
    
    def __init__(self):
        super().__init__()
        DBSessionMixin.__init__(self)
        self.logger = Logger("ProxyImplementationUpgradeHandler")
        self.telegram = TelegramService.get_instance()
        self.explorer = EVMExplorer()
        
    @classmethod
    def get_triggers(cls) -> list[HandlerTrigger]:
        """Get list of triggers this handler listens for"""
        return [HandlerTrigger.BLOCKCHAIN_EVENT]
        
    async def handle(self) -> None:
        """Handle blockchain events"""
        if not self.context:
            self.logger.error("No context provided")
            return
            
        try:
            # Extract event data
            source = self.context.get("source", "unknown")
            payload = self.context.get("payload", {})
            self.logger.info(f"Processing event from {source}", extra_data={"payload": payload})
            
            # Extract contract address and implementation address from logs
            contract_address = None
            implementation_address = None
            
            logs = payload.get('logs', [])
            self.logger.info(f"Found {len(logs)} logs in payload")
            
            for log in logs:
                topics = log.get('topics', [])
                self.logger.info(f"Processing log with {len(topics)} topics", extra_data={"topics": topics})
                
                # We should extract the contract address from the log here
                # But for the sake of testing this handler, we'll use a known address from an Immunefi bounty

                contract_address = "0x60a91E2B7A1568f0848f3D43353C453730082E46"
                implementation_address = "0x41912d95d040ecc7d715e5115173d37e4e7cb24e"

                # if len(topics) >= 2 and topics[0] == "0x5c60da1bfc44b1d9d98cb2ef4f38f1f918db61f20e5392ae39893172435edaba":
                #     contract_address = log.get('address')
                #     # Extract implementation address from first argument
                #     implementation_address = "0x" + topics[1][-40:]  # Take last 20 bytes for address
                #     self.logger.info(f"Found upgrade event - Contract: {contract_address}, Implementation: {implementation_address}")
                #     break
            
            if not contract_address or not implementation_address:
                self.logger.debug("No proxy upgrade event found in payload")
                return
                
            # Look up project info from database
            project_info = await self._get_project_info(contract_address)
            self.logger.info("Project info lookup result", extra_data={"project_info": project_info})
            
            # Prepare data for agent
            agent_data = {
                "contract_address": contract_address,
                "implementation_address": implementation_address,
                "transaction_hash": payload.get('transactionHash'),
                "block_number": payload.get('blockNumber'),
                "project": project_info
            }
            
            # Call agent to analyze implementation
            await self._analyze_implementation(agent_data)
            
        except Exception as e:
            self.logger.error(f"Error handling proxy implementation upgrade event: {str(e)}")
            
    async def _get_project_info(self, contract_address: str) -> Optional[Dict[str, Any]]:
        """Get project info for a contract address from database"""
        try:
            async with self.get_async_session() as session:
                query = text("""
                    SELECT 
                        p.id,
                        p.name,
                        p.description,
                        p.project_type,
                        p.extra_data,
                        a.source_url,
                        a.asset_type
                    FROM assets a
                    JOIN project_assets pa ON a.id = pa.asset_id
                    JOIN projects p ON pa.project_id = p.id
                    WHERE LOWER(a.source_url) LIKE LOWER(:address)
                    AND p.project_type = 'bounty'
                    LIMIT 1
                """)
                
                result = await session.execute(
                    query, 
                    {"address": f"%{contract_address}%"}
                )
                row = result.first()
                
                if row:
                    # Extract bounty info from extra_data
                    extra_data = row.extra_data or {}
                    max_bounty = extra_data.get('max_bounty', 0) if isinstance(extra_data, dict) else 0
                    
                    return {
                        "id": row.id,
                        "name": row.name,
                        "description": row.description,
                        "project_type": row.project_type,
                        "max_bounty": max_bounty,
                        "source_url": row.source_url,
                        "asset_type": row.asset_type,
                        "extra_data": extra_data
                    }
                    
                return None
                
        except Exception as e:
            self.logger.error(f"Error querying project info: {str(e)}\nTraceback: {traceback.format_exc()}")
            return None
            
    async def _fetch_source_code(self, address: str) -> Optional[str]:
        """Fetch verified source code from Etherscan
        
        Args:
            address: Contract address to fetch source for
            
        Returns:
            Source code if found, None otherwise
        """
        try:
            # Get API key and URL for Etherscan
            api_key = self.explorer.get_api_key(ExplorerType.ETHERSCAN)
            api_url = self.explorer.get_api_url(ExplorerType.ETHERSCAN)
            
            # Construct API URL
            full_api_url = f"{api_url}?module=contract&action=getsourcecode&address={address}&apikey={api_key}"
            
            # Fetch source code
            async with aiohttp.ClientSession() as session:
                async with session.get(full_api_url) as response:
                    data = await response.json()
            
            if data["status"] != "1":
                self.logger.error(f"Etherscan API error: {data.get('message', 'Unknown error')}")
                return None
            
            # Extract source code
            result = data["result"][0]
            source_code = result.get("SourceCode", "")
            
            if not source_code:
                return None
                
            try:
                # Handle double-wrapped JSON (starts with {{ and ends with }})
                if source_code.startswith('{{') and source_code.endswith('}}'):
                    # Remove the double braces
                    source_code = source_code[1:-1].strip()
                    
                # Parse the JSON
                source_data = json.loads(source_code)
                
                # Combine all source files into one string
                combined_source = []
                for filename, filedata in source_data.get("sources", {}).items():
                    content = filedata.get("content", "")
                    combined_source.append(f"// File: {filename}\n{content}\n")
                    
                return "\n".join(combined_source)
                
            except json.JSONDecodeError:
                # If not JSON, return the source code as is
                return source_code
                
        except Exception as e:
            self.logger.error(f"Error fetching source code: {str(e)}\nTraceback: {traceback.format_exc()}")
            return None
            
    async def _analyze_implementation(self, data: Dict[str, Any]) -> None:
        """Analyze implementation using agent"""
        try:
            # Get verified source code
            self.logger.info(f"Fetching source code for {data['implementation_address']}")
            source_code = await self._fetch_source_code(data['implementation_address'])
            if not source_code:
                self.logger.error("Could not fetch verified source code")
                return
                
            self.logger.info("Initializing agent for analysis")
            # Initialize agent
            agent = ProxyImplementationUpgradeAgent()
            
            # Get analysis from agent
            self.logger.info("Starting implementation analysis")
            analysis = await agent.analyze_implementation(source_code)
            self.logger.info("Analysis complete", extra_data={"analysis": analysis})
            
            # Format notification message
            message = [
                "🔄 Proxy Implementation Upgrade In Bounty Scope Detected!",
                "",
                f"Contract: https://etherscan.io/address/{data['contract_address']}",
                f"New Implementation: https://etherscan.io/address/{data['implementation_address']}",
                f"Transaction: https://etherscan.io/tx/{data['transaction_hash']}",
                "",
            ]
            
            # Add project info if available
            if data.get('project'):
                project = data['project']
                message.extend([
                    "Project Information:",
                    f"Name: {project['name']}",
                    f"Max Bounty: ${project['max_bounty']:,.2f}" if project.get('max_bounty') else "Max Bounty: Not specified",
                    f"Description: {project['description']}" if project.get('description') else "",
                    ""
                ])
            
            # Format analysis results
            analysis_message = agent.format_analysis(analysis)
            message.append(analysis_message)
            
            # Send notification
            self.logger.info("Sending notification")
            await self.telegram.send_message("\n".join(message))
            
        except Exception as e:
            self.logger.error(f"Error analyzing implementation: {str(e)}\nTraceback: {traceback.format_exc()}")

# Function to initialize and register the handler
def initialize(registry):
    """Initialize and register the handler
    
    Args:
        registry: The handler registry to register with
    """
    handler = ProxyImplementationUpgradeHandler()
    registry.register_handler(handler) 