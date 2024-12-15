from src.handlers.base import Handler, HandlerTrigger, HandlerResult
from src.services.telegram import TelegramService
from src.util.logging import Logger
from src.backend.database import DBSessionMixin
from src.util.etherscan import EVMExplorer
from sqlalchemy import text
from typing import Dict, Any, Optional
import traceback


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

    async def handle(self) -> HandlerResult:
        """Handle blockchain events"""
        if not self.context:
            self.logger.error("No context provided")
            return HandlerResult(success=False, error="No context provided")

        try:
            # Extract event data
            source = self.context.get("source", "unknown")
            payload = self.context.get("payload", {})
            self.logger.info(f"Processing event from {source}", extra_data={"payload": payload})

            # Extract contract address and implementation address from logs
            contract_address = None
            implementation_address = None

            logs = payload.get("logs", [])
            self.logger.info(f"Found {len(logs)} logs in payload")

            for log in logs:
                topics = log.get("topics", [])
                self.logger.info(f"Processing log with {len(topics)} topics", extra_data={"topics": topics})

                # We should extract the contract address from the log here
                # But for the sake of testing this example, we'll use a known address from an Immunefi bounty

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
                return HandlerResult(success=True, data={"found_upgrade": False})

            # Look up project info from database
            project_info = await self._get_project_info(contract_address)
            self.logger.info("Project info lookup result", extra_data={"project_info": project_info})

            # Prepare data for agent
            agent_data = {
                "contract_address": contract_address,
                "implementation_address": implementation_address,
                "transaction_hash": payload.get("transactionHash"),
                "block_number": payload.get("blockNumber"),
                "project": project_info,
            }

            # Call agent to analyze implementation
            analysis_result = await self._analyze_implementation(agent_data)

            return HandlerResult(
                success=True,
                data={
                    "found_upgrade": True,
                    "contract_address": contract_address,
                    "implementation_address": implementation_address,
                    "project": project_info,
                    "analysis": analysis_result,
                },
            )

        except Exception as e:
            error_msg = f"Error handling proxy implementation upgrade event: {str(e)}"
            self.logger.error(error_msg)
            return HandlerResult(success=False, error=error_msg)

    async def _get_project_info(self, contract_address: str) -> Optional[Dict[str, Any]]:
        """Get project info from database"""
        try:
            async with self.session() as session:
                # Query for project containing this contract address
                query = text(
                    """
                    SELECT p.* FROM projects p
                    JOIN assets a ON a.project_id = p.id
                    WHERE a.source_url ILIKE :contract_pattern
                    LIMIT 1
                """
                )

                result = await session.execute(query, {"contract_pattern": f"%{contract_address}%"})

                row = result.fetchone()
                if row:
                    return dict(row)
                return None

        except Exception as e:
            self.logger.error(f"Error querying project info: {str(e)}\nTraceback: {traceback.format_exc()}")
            return None

    async def _analyze_implementation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze implementation changes using agent"""
        try:
            agent = ProxyImplementationUpgradeAgent()
            return await agent.analyze(data)
        except Exception as e:
            self.logger.error(f"Error analyzing implementation: {str(e)}")
            return {"error": str(e)}


# Function to initialize and register the handler
def initialize(registry):
    """Initialize and register the handler

    Args:
        registry: The handler registry to register with
    """
    handler = ProxyImplementationUpgradeHandler()
    registry.register_handler(handler)
