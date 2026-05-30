"""Logging configuration for RefChecker using structlog.

Provides a configured structlog setup with console output,
color support, and structured JSON logging option.
"""

import logging
import sys
from typing import Any

import structlog


def configure_logging(
    *,
    level: str = "INFO",
    json_format: bool = False,
) -> None:
    """Configure structlog for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_format: If True, output JSON-formatted logs.
            Defaults to False (human-readable console output).
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Configure stdlib logging to capture warnings from third-party libs
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=log_level,
    )

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if json_format:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.plain_traceback,
        )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Apply formatter to the root stdlib handler
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processors=[
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    renderer,
                ],
            )
        )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name, typically __name__ of the calling module.

    Returns:
        A configured structlog BoundLogger.
    """
    return structlog.get_logger(name)
