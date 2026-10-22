"""
services/privacy.py — Privacy-safe logging helpers.
NEVER log patient names, record contents, test values, or file contents.
Log only: request_id, endpoint, status, stage, duration, counts.
"""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import contextmanager
from typing import Generator

logger = logging.getLogger("health_copilot")


def get_request_id() -> str:
    return str(uuid.uuid4())[:8]


@contextmanager
def log_stage(stage: str, request_id: str = "") -> Generator[None, None, None]:
    """Log pipeline stage entry/exit with timing. Never log content."""
    start = time.perf_counter()
    logger.info("[%s] Stage '%s' started", request_id or "-", stage)
    try:
        yield
        elapsed = (time.perf_counter() - start) * 1000
        logger.info("[%s] Stage '%s' completed in %.1fms", request_id or "-", stage, elapsed)
    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000
        logger.warning(
            "[%s] Stage '%s' failed after %.1fms: %s",
            request_id or "-", stage, elapsed, type(exc).__name__
        )
        raise


def log_upload(request_id: str, profile_id: str, ext: str, size_bytes: int) -> None:
    """Log upload metadata only — no filename, no content."""
    logger.info(
        "[%s] Upload: profile=[redacted] ext=%s size=%d bytes",
        request_id, ext, size_bytes
    )


def log_record_event(request_id: str, record_id: str, event: str) -> None:
    """Log a record lifecycle event."""
    logger.info("[%s] Record event=%s record_id=%s", request_id, event, record_id)


def log_error(request_id: str, code: str, status: int) -> None:
    """Log error code and status — no patient data."""
    logger.warning("[%s] Error code=%s status=%d", request_id, code, status)
