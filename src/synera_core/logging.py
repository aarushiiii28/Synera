"""Structured logging configuration for SYNERA."""

import logging
import sys

from rich.console import Console
from rich.logging import RichHandler


def get_logger(name: str = "synera") -> logging.Logger:
    """Return a configured structured logger with Rich handler."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        console = Console(file=sys.stderr)
        handler = RichHandler(
            console=console,
            show_time=True,
            show_path=False,
            rich_tracebacks=True,
        )
        formatter = logging.Formatter("%(message)s", datefmt="[%X]")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False
    return logger
