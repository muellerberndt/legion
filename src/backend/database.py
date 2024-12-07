from contextlib import contextmanager, asynccontextmanager
from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from src.config.config import Config
import os

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
                # Convert to asyncpg URL for async engine
                async_url = database_url.replace("postgres://", "postgresql+asyncpg://")
                # Convert to psycopg2 URL for sync engine
                database_url = database_url.replace("postgres://", "postgresql://")
            else:
                # Fallback to config-based URL
                db_config = config.get("database", {})
                database_url = f"postgresql://{db_config.get('user')}:{db_config.get('password')}@{db_config.get('host')}:{db_config.get('port')}/{db_config.get('name')}"
                async_url = f"postgresql+asyncpg://{db_config.get('user')}:{db_config.get('password')}@{db_config.get('host')}:{db_config.get('port')}/{db_config.get('name')}"

            # Create sync engine
            self._engine = create_engine(database_url, future=True)
            self._SessionLocal = sessionmaker(bind=self._engine, expire_on_commit=False)

            # Create async engine
            self._async_engine = create_async_engine(async_url, future=True)
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
