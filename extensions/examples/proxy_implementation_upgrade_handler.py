from src.handlers.base import Handler, HandlerTrigger, HandlerResult
from src.services.telegram import TelegramService
from src.util.logging import Logger
from src.backend.database import DBSessionMixin
from src.util.etherscan import EVMExplorer
from sqlalchemy import text
from src.jobs.autobot import AutobotJob
from src.jobs.manager import JobManager
from src.config.config import Config


class ProxyImplementationUpgradeHandler(Handler, DBSessionMixin):
    """Handler for monitoring proxy implementation upgrades"""

    def __init__(self):
        super().__init__()
        DBSessionMixin.__init__(self)
        self.logger = Logger("ProxyImplementationUpgradeHandler")
        self.telegram = TelegramService.get_instance()
        self.explorer = EVMExplorer()
        self.config = Config()

    @classmethod
    def get_triggers(cls) -> list[HandlerTrigger]:
        """Get list of triggers this handler listens for"""
        return [HandlerTrigger.BLOCKCHAIN_EVENT]

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

            # Create prompt for Autobot
            prompt = (
                f"The implementation of the proxy {contract_address} was just upgraded. "
                f"Check if the proxy is associated with any bounty (search assets by source_url) and if so, "
                f"provide a brief summary including the project details."
            )

            # Create and submit AutobotJob
            job = AutobotJob(prompt=prompt)
            job_manager = await JobManager.get_instance()
            job_id = await job_manager.submit_job(job)

            return HandlerResult(
                success=True,
                data={
                    "found_upgrade": True,
                    "contract_address": contract_address,
                    "implementation_address": implementation_address,
                    "job_id": job_id,
                },
            )

        except Exception as e:
            error_msg = f"Error handling proxy implementation upgrade event: {str(e)}"
            self.logger.error(error_msg)
            return HandlerResult(success=False, data={"error": error_msg})  # Put error in data dict instead
