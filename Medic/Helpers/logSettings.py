"""Logging configuration for Medic."""
import os
import logging

# Log level mapping
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def logSetup() -> int:
    """
    Get the configured log level.

    Uses LOG_LEVEL environment variable if set, otherwise defaults to WARNING.

    Returns:
        Logging level as integer
    """
    level_name = os.environ.get("LOG_LEVEL", "WARNING").upper()
    return LOG_LEVELS.get(level_name, logging.WARNING)


def configure_logging():
    """Configure logging for the application."""
    level = logSetup()
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
