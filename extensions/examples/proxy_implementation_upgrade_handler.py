from src.handlers.base import Handler, HandlerTrigger, HandlerResult
from src.services.db_notification_service import DatabaseNotificationService
from src.util.logging import Logger
from src.backend.database import DBSessionMixin
from src.util.etherscan import EVMExplorer
from src.config.config import Config
from src.backend.query_builder import QueryBuilder


class ProxyImplementationUpgradeHandler(Handler, DBSessionMixin):
    """Example for a custom handler that reacts to proxy implementation upgrades.

    This example demonstrates how to register for a specific trigger, handle incoming events,
    and pre-filter the data. One could add more sophisticated handling here.

    In the latest version of the framework, this handler is redundant as the ProxyMonitorJob will handle this.
    """

    def __init__(self):
        super().__init__()
        DBSessionMixin.__init__(self)
        self.logger = Logger("ProxyImplementationUpgradeHandler")
        self.notification_service = DatabaseNotificationService.get_instance()
        self.explorer = EVMExplorer()
        self.config = Config()

    @classmethod
    def get_triggers(cls) -> list[HandlerTrigger]:
        """Get list of triggers this handler listens for"""
        return [HandlerTrigger.BLOCKCHAIN_EVENT]

    async def is_contract_in_scope(self, contract_address: str) -> bool:
        """Check if a contract address is in scope by comparing with deployed contract assets"""
        try:
            async with self.get_async_session() as session:
                # Build query to find matching deployed contracts
                query = (
                    QueryBuilder()
                    .from_table("assets")
                    .select("assets.id")
                    .where("asset_type", "=", "deployed_contract")
                    .where("identifier", "contains", contract_address.lower())
                    .build()
                )

                # Execute query
                result = await session.execute(query)
                matches = result.fetchall()

                in_scope = len(matches) > 0
                self.logger.info(
                    f"Contract {contract_address} scope check", extra_data={"in_scope": in_scope, "matches": len(matches)}
                )
                return in_scope

        except Exception as e:
            self.logger.error(f"Error checking contract scope: {str(e)}")
            return False

    async def handle(self) -> HandlerResult:
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

                if len(topics) >= 2 and topics[0] == "0xbc7cd75a20ee27fd9adebab32041f755214dbc6bffa90cc0225b39da2e5c2d3b":
                    contract_address = log.get("address")
                    # Extract implementation address from first argument
                    implementation_address = "0x" + topics[1][-40:]  # Take last 20 bytes for address
                    self.logger.info(
                        f"Found upgrade event - Contract: {contract_address}, Implementation: {implementation_address}"
                    )
                    break

            if not contract_address or not implementation_address:
                self.logger.debug("No proxy upgrade event found in payload")
                return HandlerResult(success=True, data={"found_upgrade": False})

            # Check if contract is in scope
            if not await self.is_contract_in_scope(contract_address):
                self.logger.info(f"Contract {contract_address} not in scope, ignoring upgrade")
                return HandlerResult(success=True, data={"found_upgrade": True, "in_scope": False})

            # We should add better handling here:
            # - Store the new implementation in the assets table
            # - Do a diff between the old and new implementation
            # - Give the diff to the LLM to analyze
            # - Only the user if the upgrade is significant
            # - Add project details to the message

            message_lines = [
                "🔄 Proxy Implementation Upgrade Detected",
                f"\nProxy Contract: {contract_address}",
                f"New Implementation: {implementation_address}",
            ]

            # Send notification
            message = "\n".join(message_lines)
            await self.notification_service.send_message(message)

            return HandlerResult(
                success=True,
                data={
                    "found_upgrade": True,
                    "in_scope": True,
                    "contract_address": contract_address,
                    "implementation_address": implementation_address,
                    "message": message,
                },
            )

        except Exception as e:
            error_msg = f"Error handling proxy implementation upgrade event: {str(e)}"
            self.logger.error(error_msg)
            return HandlerResult(success=False, data={"error": error_msg})
