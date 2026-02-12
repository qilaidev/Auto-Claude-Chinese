"""
Logging configuration for Auto Claude.

Enabled only when AUTO_CLAUDE_LOG_FILE or AUTO_CLAUDE_LOG_DIR is set.
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_BACKUP_COUNT = 3


def _int_env(name: str, default: int, *, minimum: int = 0) -> int:
    value = os.environ.get(name)
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    if parsed < minimum:
        return default
    return parsed


def _warn_logging_disabled(reason: str) -> None:
    """Emit a concise warning when file logging cannot be initialized."""
    print(f"[auto-claude] file logging disabled: {reason}", file=sys.stderr)


def configure_logging(project_dir: Path | None = None) -> Path | None:
    """
    Configure file logging if enabled via environment variables.

    Returns the log file path if configured, otherwise None.
    """
    log_file = os.environ.get("AUTO_CLAUDE_LOG_FILE")
    log_dir = os.environ.get("AUTO_CLAUDE_LOG_DIR")

    if not log_file and not log_dir:
        return None

    if log_file:
        path = Path(log_file)
    else:
        path = Path(log_dir) / "auto-claude.log"

    if not path.is_absolute() and project_dir:
        path = project_dir / path

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _warn_logging_disabled(f"cannot create log directory '{path.parent}': {exc}")
        return None

    level_name = os.environ.get("AUTO_CLAUDE_LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()
    level = getattr(logging, level_name, logging.INFO)
    max_bytes = _int_env("AUTO_CLAUDE_LOG_MAX_BYTES", DEFAULT_MAX_BYTES, minimum=1)
    backup_count = _int_env("AUTO_CLAUDE_LOG_BACKUPS", DEFAULT_BACKUP_COUNT, minimum=0)

    try:
        handler = RotatingFileHandler(
            path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
    except OSError as exc:
        _warn_logging_disabled(f"cannot open log file '{path}': {exc}")
        return None

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=level, handlers=[handler])
    else:
        root.addHandler(handler)
        if root.level == logging.NOTSET:
            root.setLevel(level)

    return path
