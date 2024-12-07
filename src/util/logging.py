from datetime import datetime
from typing import Optional, Any, Dict
import json
import logging
from src.models.base import LogEntry, LogLevel
from src.backend.database import DBSessionMixin


class ModelJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for SQLAlchemy models"""

    def default(self, obj):
        if hasattr(obj, "__dict__"):
            # Filter out SQLAlchemy internal attributes
            return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
        return super().default(obj)


class LogConfig:
    """Global logging configuration"""

    _verbose = False
    _db_logging = True  # New flag to control database logging
    _log_level = logging.INFO

    @classmethod
    def configure_logging(cls, level: str = "INFO"):
        """Configure logging globally"""
        # Map string levels to logging constants
        level_map = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR}

        # Set level, defaulting to INFO if invalid
        cls._log_level = level_map.get(level.upper(), logging.INFO)

        # Configure Python's logging
        logging.basicConfig(
            level=cls._log_level, format="[%(asctime)s] %(levelname)s - %(name)s - %(message)s", datefmt="%Y-%m-%dT%H:%M:%S.%f"
        )

    @classmethod
    def set_verbose(cls, verbose: bool):
        cls._verbose = verbose
        cls.configure_logging("DEBUG" if verbose else "INFO")

    @classmethod
    def set_log_level(cls, level: str):
        """Set the log level directly"""
        cls.configure_logging(level)

    @classmethod
    def is_verbose(cls) -> bool:
        return cls._verbose

    @classmethod
    def set_db_logging(cls, enabled: bool):
        cls._db_logging = enabled

    @classmethod
    def is_db_logging_enabled(cls) -> bool:
        return cls._db_logging


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
        # Format message with extra_data if present
        log_message = message
        if extra_data:
            # Format extra_data as pretty JSON
            extra_json = json.dumps(extra_data, indent=2, cls=ModelJSONEncoder)
            log_message = f"{message}\n{extra_json}"

        # Log to Python's logging system
        log_func = getattr(self.python_logger, level.value.lower())
        log_func(log_message)

        if not LogConfig.is_db_logging_enabled():
            return

        try:
            # Serialize extra_data with custom encoder
            if extra_data:
                extra_data = json.loads(json.dumps(extra_data, cls=ModelJSONEncoder))

            # Create log entry
            log_entry = LogEntry(level=level, message=message, source=self.source, extra_data=extra_data)

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
