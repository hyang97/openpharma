"""
Logging configuration for OpenPharma.
Provides consistent logging across all modules.
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler


def setup_logging(level: str = "INFO", log_file: str = None):
    """
    Configure logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file. If None, only logs to console.
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    simple_formatter = logging.Formatter(
        fmt='%(levelname)s - %(message)s'
    )

    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(detailed_formatter)

    # Handlers list
    handlers = [console_handler]

    # File handler with rotation (optional)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Rotate after 10MB, keep 5 backup files
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(detailed_formatter)
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        handlers=handlers,
        force=True  # Override any existing configuration
    )

    # Set third-party loggers to WARNING to reduce noise
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured at {level} level")
    if log_file:
        logger.info(f"Logging to file: {log_file}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    Args:
        name: Usually __name__ from the calling module

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
