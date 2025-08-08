from contextlib import contextmanager, asynccontextmanager
from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from src.config.config import Config
import os
from urllib.parse import urlparse, parse_qs

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
            database_url = config.database_url

            if not database_url:
                if config._test_mode:
                    sync_url = "sqlite:///./test.db"
                    async_url = "sqlite+aiosqlite:///./test.db"
                    connect_args_sync = {}
                    connect_args_async = {}
                else:
                    raise ValueError("Database configuration is incomplete and not in test mode.")
            else:
                parsed = urlparse(database_url)
                if parsed.scheme.startswith("sqlite"):
                    sync_url = database_url
                    async_url = database_url.replace("sqlite:///", "sqlite+aiosqlite:///")
                    connect_args_sync = {}
                    connect_args_async = {}
                elif parsed.scheme.startswith("postgres"):
                    # Handle fly.io postgres URL with params
                    if "sslmode" in parse_qs(parsed.query):
                        base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                        async_url = base_url.replace("postgres://", "postgresql+asyncpg://")
                        sync_url = base_url.replace("postgres://", "postgresql://")
                        params = parse_qs(parsed.query)
                        connect_args_async = {"ssl": params["sslmode"][0] != "disable"}
                        connect_args_sync = {"sslmode": params["sslmode"][0]}
                    else:  # standard postgres
                        sync_url = database_url.replace("postgres://", "postgresql://")
                        async_url = database_url.replace("postgres://", "postgresql+asyncpg://")
                        connect_args_sync = {}
                        connect_args_async = {}
                else:
                    raise ValueError(f"Unsupported database scheme: {parsed.scheme}")

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
