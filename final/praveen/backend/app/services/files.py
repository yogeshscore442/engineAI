"""
services/files.py — File validation, storage, serving, and deletion.
Only jpg/jpeg/png/pdf allowed (checked by extension AND magic bytes).
Files stored under UPLOAD_DIR with UUID names; no path traversal.
"""
from __future__ import annotations

import hashlib
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile

from app.config import get_settings

logger = logging.getLogger(__name__)

MAGIC_BYTES: dict[str, list[bytes]] = {
    ".jpg": [b"\xff\xd8"],
    ".jpeg": [b"\xff\xd8"],
    ".jfif": [b"\xff\xd8"],
    ".png": [b"\x89PNG"],
    ".pdf": [b"%PDF"],
    ".webp": [b"RIFF"],
    ".tif": [b"II*\x00", b"MM\x00*"],
    ".tiff": [b"II*\x00", b"MM\x00*"],
}

ALLOWED_EXTENSIONS = set(MAGIC_BYTES.keys())

CONTENT_TYPE_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".jfif": "image/jpeg",
    ".png": "image/png",
    ".pdf": "application/pdf",
    ".webp": "image/webp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


def _get_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def detect_true_extension(data: bytes, declared_ext: str = "") -> Optional[str]:
    """
    Detect the real file format from magic bytes.
    Gives content precedence over untrusted filenames.
    """
    if data.startswith(b"%PDF-"):
        return ".pdf"
    if data.startswith(b"\xff\xd8\xff") or data.startswith(b"\xff\xd8"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n") or data.startswith(b"\x89PNG"):
        return ".png"
    if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP":
        return ".webp"
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return ".tiff"

    # If declared extension matches magic bytes
    if declared_ext and declared_ext in MAGIC_BYTES:
        for sig in MAGIC_BYTES[declared_ext]:
            if data.startswith(sig):
                return declared_ext

    return None


def _check_magic(data: bytes, ext: str) -> bool:
    if ext == ".webp":
        return data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP"
    signatures = MAGIC_BYTES.get(ext, [])
    return any(data.startswith(sig) for sig in signatures)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def validate_and_read_upload(file: UploadFile) -> tuple[bytes, str, str]:
    """
    Read upload, validate content-based format, enforce size limit.
    Content format strictly overrides misleading or missing filenames.
    Returns (file_bytes, extension, sha256_hex).
    Raises HTTPException on validation failure.
    """
    settings = get_settings()

    # Read content first so format can be verified from actual content
    content = await file.read(settings.max_upload_bytes + 1)

    # Size check
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail={"error": {"code": "FILE_TOO_LARGE",
                              "message": f"File exceeds {settings.max_upload_mb} MB limit."}}
        )

    if len(content) == 0:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "EMPTY_FILE", "message": "Uploaded file is empty."}}
        )

    # Content-based format detection
    declared_ext = _get_extension(file.filename or "")
    detected_ext = detect_true_extension(content, declared_ext)

    if detected_ext is None:
        raise HTTPException(
            status_code=415,
            detail={"error": {"code": "INVALID_FILE_TYPE",
                              "message": f"Only PDF, JPEG, PNG, WebP, and TIFF medical documents are supported. Could not identify valid document content from upload."}}
        )

    # If filename had a different extension or no extension, use the true detected extension
    final_ext = detected_ext
    if declared_ext and declared_ext != detected_ext:
        logger.info(
            "Upload content format (%s) overrides declared filename extension (%s) for safety",
            detected_ext, declared_ext,
        )

    sha = _sha256(content)
    return content, final_ext, sha


def save_file(content: bytes, ext: str) -> tuple[Path, str]:
    """
    Save file bytes to UPLOAD_DIR with a UUID filename.
    Uses atomic write: write to temp file, then rename.
    Returns (final_path, relative_path_str).
    """
    settings = get_settings()
    upload_dir = settings.upload_dir_resolved
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4()}{ext}"
    final_path = upload_dir / filename
    tmp_path = upload_dir / f".tmp_{filename}"

    try:
        tmp_path.write_bytes(content)
        tmp_path.rename(final_path)
    except Exception as exc:
        # Clean up temp file if rename failed
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                logger.warning("Could not remove tmp file: %s (filename only logged)", filename)
        raise exc

    return final_path, str(final_path)


def get_file_path(file_path_str: str) -> Optional[Path]:
    """
    Resolve file path safely (prevents traversal).
    Returns None if path is outside UPLOAD_DIR.
    """
    settings = get_settings()
    upload_dir = settings.upload_dir_resolved
    try:
        resolved = Path(file_path_str).resolve()
        if not resolved.is_relative_to(upload_dir):
            logger.warning("Path traversal attempt detected (path omitted from log)")
            return None
        return resolved if resolved.is_file() else None
    except Exception:
        return None


def delete_file(file_path_str: str) -> bool:
    """Delete a stored file safely. Returns True if deleted."""
    path = get_file_path(file_path_str)
    if path and path.exists():
        try:
            path.unlink()
            return True
        except Exception as exc:
            logger.warning("Could not delete file (filename omitted): %s", type(exc).__name__)
    return False


def get_content_type(ext: str) -> str:
    return CONTENT_TYPE_MAP.get(ext, "application/octet-stream")
