from datetime import datetime
from typing import Optional, Any, Dict
import click
import json
import logging
from src.models.base import LogEntry, LogLevel
from src.backend.database import DBSessionMixin
import enum

class ModelJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for SQLAlchemy models"""
    def default(self, obj):
        if hasattr(obj, '__dict__'):
            # Filter out SQLAlchemy internal attributes
            return {k: v for k, v in obj.__dict__.items() 
                   if not k.startswith('_')}
        return super().default(obj)

class LogConfig:
    """Global logging configuration"""
    _verbose = False
    _db_logging = True  # New flag to control database logging
    
    @classmethod
    def configure_logging(cls, verbose: bool = False):
        """Configure logging globally"""
        cls._verbose = verbose
        
        # Configure Python's logging
        level = logging.INFO if verbose else logging.WARNING
        logging.basicConfig(
            level=level,
            format='[%(asctime)s] %(levelname)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%dT%H:%M:%S.%f'
        )

    @classmethod
    def set_verbose(cls, verbose: bool):
        cls._verbose = verbose
        cls.configure_logging(verbose)

    @classmethod
    def is_verbose(cls) -> bool:
        return cls._verbose

    @classmethod
    def set_db_logging(cls, enabled: bool):
        cls._db_logging = enabled

    @classmethod
    def is_db_logging_enabled(cls) -> bool:
        return cls._db_logging

class LogLevel(str, enum.Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

class Logger(DBSessionMixin):
    """
    Central logging service that handles both database and console logging
    """
    def __init__(self, source: str):
        """
        Initialize logger
        
        Args:
            source: Name of the component/module using the logger
        """
        super().__init__()
        self._session = None
        self.source = source
        self.python_logger = logging.getLogger(source)

    def _log(self, level: LogLevel, message: str, extra_data: Optional[Dict[str, Any]] = None) -> None:
        """Internal method to handle logging"""
        # Always log to Python's logging system
        log_func = getattr(self.python_logger, level.value.lower())
        log_func(message)
        
        if not LogConfig.is_db_logging_enabled():
            return

        try:
            # Serialize extra_data with custom encoder
            if extra_data:
                extra_data = json.loads(
                    json.dumps(extra_data, cls=ModelJSONEncoder)
                )

            # Create log entry
            log_entry = LogEntry(
                level=level,
                message=message,
                source=self.source,
                extra_data=extra_data
            )

            # Store in database
            with self.get_session() as session:
                session.add(log_entry)
                session.commit()

        except Exception as e:
            # Fallback to print on logging error
            print(f"[{datetime.utcnow().isoformat()}] ERROR - Logging failed: {str(e)}")
            print(f"Original message: [{level.value}] {message}")

    def debug(self, message: str, extra_data: Optional[Dict[str, Any]] = None) -> None:
        """Log a debug message"""
        self._log(LogLevel.DEBUG, message, extra_data)

    def info(self, message: str, extra_data: Optional[Dict[str, Any]] = None) -> None:
        """Log an info message"""
        self._log(LogLevel.INFO, message, extra_data)

    def warning(self, message: str, extra_data: Optional[Dict[str, Any]] = None) -> None:
        """Log a warning message"""
        self._log(LogLevel.WARNING, message, extra_data)

    def error(self, message: str, extra_data: Optional[Dict[str, Any]] = None) -> None:
        """Log an error message"""
        self._log(LogLevel.ERROR, message, extra_data) 