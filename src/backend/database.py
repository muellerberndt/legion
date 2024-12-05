from contextlib import contextmanager
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from src.config.config import Config

# Create base class for models
Base = declarative_base()

class Database:
    _instance = None
    _engine = None
    _SessionLocal = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._engine is None:
            config = Config()
            db_config = config.get('database', {})
            database_url = f"postgresql://{db_config.get('user')}:{db_config.get('password')}@{db_config.get('host')}:{db_config.get('port')}/{db_config.get('name')}"
            self._engine = create_engine(database_url, future=True)
            self._SessionLocal = sessionmaker(bind=self._engine, expire_on_commit=False)

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
            
    def get_engine(self):
        """Get the SQLAlchemy engine instance."""
        return self._engine
            
    def is_initialized(self) -> bool:
        """Check if database is initialized by checking if tables exist"""
        inspector = inspect(self._engine)
        # Check for a core table that should exist if DB is initialized
        return 'projects' in inspector.get_table_names()

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