from contextlib import contextmanager, asynccontextmanager
from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from src.config.config import Config
import os
from urllib.parse import urlparse, parse_qs

# from src.util.logging import Logger

# Create base class for models
Base = declarative_base()


class Database:
    _instance = None
    _engine = None
    _async_engine = None
    _SessionLocal = None
    _AsyncSessionLocal = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._engine is None:
            config = Config()

            # Check for Fly's DATABASE_URL first
            database_url = os.getenv("DATABASE_URL")
            if database_url:
                # Parse the URL and its parameters
                parsed = urlparse(database_url)
                params = parse_qs(parsed.query)

                # Build base URLs without params
                base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

                # Convert to asyncpg URL for async engine
                async_url = base_url.replace("postgres://", "postgresql+asyncpg://")

                # Handle SSL parameters for asyncpg
                connect_args_async = {}
                if "sslmode" in params:
                    connect_args_async["ssl"] = params["sslmode"][0] != "disable"

                # Convert to psycopg2 URL for sync engine
                sync_url = base_url.replace("postgres://", "postgresql://")

                # Handle SSL parameters for psycopg2
                connect_args_sync = {}
                if "sslmode" in params:
                    connect_args_sync["sslmode"] = params["sslmode"][0]

            else:
                # Fallback to config-based URL
                db_config = config.get("database", {})
                if not all(
                    key in db_config and db_config[key] is not None for key in ["host", "port", "name", "user", "password"]
                ):
                    # Use test database URL in test mode
                    if config._test_mode:
                        sync_url = "postgresql://test:test@localhost:5432/test_db"
                        async_url = "postgresql+asyncpg://test:test@localhost:5432/test_db"
                        connect_args_sync = {}
                        connect_args_async = {}
                        # logger.debug("Using test database configuration")
                    else:
                        raise ValueError("Database configuration is incomplete")
                else:
                    sync_url = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['name']}"
                    async_url = f"postgresql+asyncpg://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['name']}"
                    connect_args_sync = {}
                    connect_args_async = {}
                    # logger.debug("Using config-based database configuration")

            # Create sync engine
            self._engine = create_engine(sync_url, future=True, connect_args=connect_args_sync)
            self._SessionLocal = sessionmaker(bind=self._engine, expire_on_commit=False)

            # Create async engine
            self._async_engine = create_async_engine(async_url, future=True, connect_args=connect_args_async)
            self._AsyncSessionLocal = sessionmaker(bind=self._async_engine, class_=AsyncSession, expire_on_commit=False)

    @contextmanager
    def session(self):
        """Provide a transactional scope around a series of operations."""
        session = self._SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @asynccontextmanager
    async def async_session(self):
        """Provide an async transactional scope around a series of operations."""
        session = self._AsyncSessionLocal()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    def get_engine(self):
        """Get the SQLAlchemy engine instance."""
        return self._engine

    def get_async_engine(self):
        """Get the async SQLAlchemy engine instance."""
        return self._async_engine

    def is_initialized(self) -> bool:
        """Check if database is initialized by checking if tables exist"""
        inspector = inspect(self._engine)
        # Check for a core table that should exist if DB is initialized
        return "projects" in inspector.get_table_names()


# Global instance
db = Database()


class DBSessionMixin:
    """Mixin to provide database session handling."""

    def __init__(self, session=None):
        self._session = session

    @contextmanager
    def get_session(self):
        """Get a database session - either the existing one or a new one."""
        if self._session is not None:
            yield self._session
        else:
            with db.session() as session:
                yield session

    @asynccontextmanager
    async def get_async_session(self):
        """Get an async database session."""
        if self._session is not None:
            yield self._session
        else:
            async with db.async_session() as session:
                yield session
