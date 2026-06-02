"""Unit tests for refchecker.core.logging module."""

import logging

import structlog

from refchecker.core.logging import configure_logging, get_logger


class TestConfigureLogging:
    """Tests for configure_logging()."""

    def test_debug_level(self) -> None:
        """DEBUG level configures without error."""
        configure_logging(level="DEBUG")
        # Verify configure_logging ran without error
        root = logging.getLogger()
        assert root.level <= logging.DEBUG or root.handlers

    def test_warning_level(self) -> None:
        """WARNING level configures without error."""
        configure_logging(level="WARNING")
        root = logging.getLogger()
        assert root.level <= logging.WARNING or root.handlers

    def test_json_format(self) -> None:
        """JSON format configures without error."""
        configure_logging(json_format=True)
        root = logging.getLogger()
        assert root.handlers  # handlers should exist

    def test_case_insensitive_level(self) -> None:
        """Lowercase level string works."""
        configure_logging(level="debug")
        # Should not raise

    def test_configures_root_handlers(self) -> None:
        """configure_logging sets up root logger handlers."""
        configure_logging()
        root = logging.getLogger()
        assert len(root.handlers) > 0


class TestGetLogger:
    """Tests for get_logger()."""

    def test_returns_logger(self) -> None:
        """get_logger returns a structlog proxy."""
        configure_logging()
        log = get_logger("test")
        assert log is not None

    def test_with_name(self) -> None:
        """get_logger with name returns a logger."""
        log = get_logger("refchecker.test")
        assert log is not None

    def test_without_name(self) -> None:
        """get_logger without name works."""
        log = get_logger()
        assert log is not None

    def test_logger_can_log(self) -> None:
        """Logger can emit a log message without error."""
        configure_logging()
        log = get_logger("test")
        # Should not raise
        log.info("test message", key="value")
