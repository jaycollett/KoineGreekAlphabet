"""Structured logging configuration for the application.

This module provides centralized logging setup with support for:
- JSON formatting for production
- Human-readable formatting for development
- Configurable log levels
- Request ID tracking for distributed tracing
"""
import logging
import sys
import json
from datetime import datetime
from typing import Any, Dict
from app.config import settings


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging in production."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON string.

        Args:
            record: Log record to format

        Returns:
            JSON-formatted log string
        """
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add any extra fields that were passed to the logger
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "quiz_id"):
            log_data["quiz_id"] = record.quiz_id
        if hasattr(record, "question_id"):
            log_data["question_id"] = record.question_id
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter):
    """Human-readable colored formatter for development."""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",      # Cyan
        "INFO": "\033[32m",       # Green
        "WARNING": "\033[33m",    # Yellow
        "ERROR": "\033[31m",      # Red
        "CRITICAL": "\033[35m",   # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors for terminal output.

        Args:
            record: Log record to format

        Returns:
            Colored, human-readable log string
        """
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging(log_level: str = None) -> None:
    """Configure application-wide logging.

    Sets up structured JSON logging for production or colored console
    logging for development.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
                   If None, uses settings.ENVIRONMENT to determine level.
    """
    if log_level is None:
        # Use INFO for production, DEBUG for development
        log_level = "INFO" if settings.is_production else "DEBUG"

    # Get numeric log level
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Create handler for stdout
    handler = logging.StreamHandler(sys.stdout)

    # Choose formatter based on environment
    if settings.is_production:
        formatter = JSONFormatter()
    else:
        formatter = ColoredFormatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.addHandler(handler)

    # Silence noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(
        f"Logging configured: level={log_level}, "
        f"environment={settings.ENVIRONMENT}, "
        f"format={'JSON' if settings.is_production else 'colored'}"
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module.

    Args:
        name: Logger name, typically __name__ of the module

    Returns:
        Configured logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing started")
        >>> logger.error("Error occurred", extra={"user_id": "123"})
    """
    return logging.getLogger(name)
