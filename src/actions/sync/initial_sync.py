from src.actions.base import BaseAction, ActionSpec
from src.indexers.immunefi import ImmunefiIndexer
from src.util.logging import Logger
from src.backend.database import DBSessionMixin


class InitialSyncAction(BaseAction, DBSessionMixin):
    """Action to perform initial data sync without triggering events"""

    spec = ActionSpec(
        name="initial_sync",
        description="Perform initial data sync (CLI only)",
    )

    def __init__(self):
        super().__init__()
        DBSessionMixin.__init__(self)
        self.logger = Logger("InitialSync")

    async def execute(self) -> str:
        """Execute initial sync"""
        try:
            self.logger.info("Starting initial sync...")

            # Initialize indexer in initialize mode
            with self.get_session() as session:
                indexer = ImmunefiIndexer(session=session, initialize_mode=True)
                await indexer.index()

            return "Initial sync completed successfully"

        except Exception as e:
            error_msg = f"Initial sync failed: {str(e)}"
            self.logger.error(error_msg)
            raise
