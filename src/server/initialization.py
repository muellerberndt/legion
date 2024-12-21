from sqlalchemy import text
from src.backend.database import db, Base, DBSessionMixin
from src.util.logging import Logger
from src.indexers.immunefi import ImmunefiIndexer


class Initializer(DBSessionMixin):
    """Handles server initialization tasks"""

    def __init__(self):
        super().__init__()
        self.logger = Logger("Initializer")

    async def init_db(self) -> str:
        """Initialize database schema and required extensions"""
        try:
            if db.is_initialized():
                return "Database already initialized"

            # First check if vector extension is available
            with self.get_session() as session:
                result = session.execute(
                    text("SELECT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector');")
                ).scalar()

                if not result:
                    self.logger.error("Vector extension is not available in the database")
                    raise RuntimeError("Vector extension is not available. Please install it first: CREATE EXTENSION vector;")

                # Create vector extension if not exists
                session.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))

                # Create array to vector conversion function if not exists
                session.execute(
                    text(
                        """
                        CREATE OR REPLACE FUNCTION array_to_vector(arr float8[])
                        RETURNS vector
                        LANGUAGE SQL
                        IMMUTABLE
                        PARALLEL SAFE
                        AS $$
                            SELECT arr::vector;
                        $$;
                        """
                    )
                )
                session.commit()

            # Create tables for both sync and async engines
            Base.metadata.create_all(db.get_engine())
            async with db.get_async_engine().begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            # Initialize vector similarity search index
            with self.get_session() as session:
                session.execute(
                    text(
                        """
                        CREATE INDEX IF NOT EXISTS asset_embedding_idx
                        ON assets
                        USING ivfflat (embedding vector_l2_ops)
                        WITH (lists = 100);
                        """
                    )
                )
                session.commit()

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
