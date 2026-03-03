"""Structured logging utility using structlog."""

import logging
import sys
from typing import Any

import structlog


def setup_logging() -> None:
    """Initialize structured logging configuration."""
    from .config import get_settings

    settings = get_settings()

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if settings.debug else logging.INFO,
    )

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if not settings.debug else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None, **initial_context: Any) -> structlog.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)
        **initial_context: Initial context fields to bind to all log entries

    Returns:
        Configured structlog bound logger
    """
    logger = structlog.get_logger(name)
    if initial_context:
        logger = logger.bind(**initial_context)
    return logger


# Pre-configured loggers for common use cases
def get_agent_logger(agent_name: str, session_id: str | None = None) -> structlog.BoundLogger:
    """Get a logger configured for agent operations."""
    context = {"agent_name": agent_name}
    if session_id:
        context["session_id"] = session_id
    return get_logger("agent", **context)


def get_discussion_logger(session_id: str) -> structlog.BoundLogger:
    """Get a logger configured for discussion operations."""
    return get_logger("discussion", session_id=session_id)


def get_api_logger() -> structlog.BoundLogger:
    """Get a logger configured for API operations."""
    return get_logger("api")
