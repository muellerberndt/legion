from sqlalchemy import text
from src.backend.database import db, Base, DBSessionMixin
from src.util.logging import Logger, LogConfig
from src.indexers.immunefi import ImmunefiIndexer


class Initializer(DBSessionMixin):
    """Handles server initialization tasks"""

    def __init__(self):
        super().__init__()
        self.logger = Logger("Initializer")

    async def init_db(self) -> str:
        """Initialize database schema"""
        try:
            # Temporarily disable database logging
            LogConfig.set_db_logging(False)

            if db.is_initialized():
                LogConfig.set_db_logging(True)
                return "Database already initialized"

            # Create tables for both sync and async engines
            Base.metadata.create_all(db.get_engine())
            async with db.get_async_engine().begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            # Create array to vector conversion function
            with self.get_session() as session:
                session.execute(
                    text(
                        """
                    CREATE OR REPLACE FUNCTION array_to_vector(IN array_input double precision[])
                    RETURNS vector
                    AS $$
                    SELECT array_input::vector
                    $$
                    LANGUAGE SQL
                    IMMUTABLE
                    PARALLEL SAFE;
                """
                    )
                )

                # Create vector similarity search index
                session.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS asset_embedding_idx
                    ON assets
                    USING ivfflat ((embedding::vector) vector_cosine_ops)
                    WITH (lists = 100);
                """
                    )
                )
                session.commit()

            # Re-enable database logging now that tables exist
            LogConfig.set_db_logging(True)

            return "Database initialized successfully"

        except Exception as e:
            self.logger.error(f"Failed to initialize database: {str(e)}")
            raise

    async def initial_sync(self) -> str:
        """Perform initial data sync without triggering events"""
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
