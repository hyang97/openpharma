"""
Demo script showing how logging works in OpenPharma.
Run this to see different log levels in action.
"""
import sys
from pathlib import Path

# Add parent directory to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.logging_config import setup_logging, get_logger

# Setup logging at DEBUG level to see everything
setup_logging(level="DEBUG", log_file="logs/demo.log")

# Get a logger for this module
logger = get_logger(__name__)

def demonstrate_log_levels():
    """Show all different log levels."""
    print("\n=== Demonstrating Log Levels ===\n")

    logger.debug("This is a DEBUG message - detailed info for debugging")
    logger.info("This is an INFO message - general informational message")
    logger.warning("This is a WARNING message - something unexpected happened")
    logger.error("This is an ERROR message - an error occurred")
    logger.critical("This is a CRITICAL message - critical failure!")

def demonstrate_formatted_messages():
    """Show formatted log messages."""
    print("\n=== Demonstrating Formatted Messages ===\n")

    chunk_count = 42
    section = "methods"
    tokens = 512

    # Using f-strings in log messages
    logger.info(f"Chunked {tokens} tokens from section '{section}' into {chunk_count} chunks")

    # Multiple variables
    doc_title = "Diabetes Management Study"
    logger.info(f"Processing document: {doc_title[:30]}...")

def demonstrate_exception_logging():
    """Show how to log exceptions."""
    print("\n=== Demonstrating Exception Logging ===\n")

    try:
        # This will cause an error
        result = 10 / 0
    except Exception as e:
        # Log with full stack trace
        logger.error(f"Division error occurred: {e}", exc_info=True)

def demonstrate_conditional_logging():
    """Show conditional logging based on level."""
    print("\n=== Demonstrating Conditional Logging ===\n")

    # These will only show if LOG_LEVEL is DEBUG
    for i in range(3):
        logger.debug(f"Processing item {i}")

    logger.info("Processing complete")

if __name__ == "__main__":
    print("This demo shows different logging features.")
    print("Logs are printed to console AND saved to logs/demo.log")
    print("-" * 60)

    demonstrate_log_levels()
    demonstrate_formatted_messages()
    demonstrate_exception_logging()
    demonstrate_conditional_logging()

    print("\n" + "=" * 60)
    print("Check logs/demo.log to see the full log file!")
    print("=" * 60)
