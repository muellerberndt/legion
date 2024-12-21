import logging


class LogConfig:
    """Global logging configuration"""

    _verbose = False
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


class Logger:
    """Simple logging service that wraps Python's logging"""

    def __init__(self, source: str):
        """Initialize logger

        Args:
            source: Name of the component/module using the logger
        """
        self.source = source
        self.python_logger = logging.getLogger(source)

    def debug(self, message: str, extra_data: dict = None) -> None:
        """Log a debug message"""
        if extra_data:
            message = f"{message} - {extra_data}"
        self.python_logger.debug(message)

    def info(self, message: str, extra_data: dict = None) -> None:
        """Log an info message"""
        if extra_data:
            message = f"{message} - {extra_data}"
        self.python_logger.info(message)

    def warning(self, message: str, extra_data: dict = None) -> None:
        """Log a warning message"""
        if extra_data:
            message = f"{message} - {extra_data}"
        self.python_logger.warning(message)

    def error(self, message: str, extra_data: dict = None) -> None:
        """Log an error message"""
        if extra_data:
            message = f"{message} - {extra_data}"
        self.python_logger.error(message)
