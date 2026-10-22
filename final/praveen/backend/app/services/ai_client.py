"""
services/ai_client.py — The ONLY place that touches ai_engine.
Defines AIClient Protocol with MockAIClient and RealAIClient.
Runs blocking AI calls in a threadpool to keep the server responsive.
Never logs patient data or file contents.
"""
from __future__ import annotations

import asyncio
import glob
import json
import logging
import os
import sys
import uuid
import tempfile
import mimetypes
from pathlib import Path
from typing import Protocol, Optional

from app.config import get_settings
from app.integration import AI_PROJECT_ROOT, BACKEND_ROOT

logger = logging.getLogger(__name__)

# Path to mock contract files
CONTRACT_DIR = BACKEND_ROOT / "contract"


class AIClient(Protocol):
    async def extract(
        self,
        file_bytes: bytes,
        filename_hint: str,
        lang: str = "en",
    ) -> dict:
        ...


# ---------------------------------------------------------------------------
# Mock AI Client
# ---------------------------------------------------------------------------
_mock_files: list[Path] = []
_mock_index = 0


def _load_mock_files() -> list[Path]:
    """Discover all mock_*.json files in contract/ directory."""
    patterns = [
        CONTRACT_DIR / "mock_*.json",
    ]
    found = []
    for pattern in patterns:
        found.extend(glob.glob(str(pattern)))
    return [Path(p) for p in sorted(set(found))]


def _pick_mock_file(doc_type: str = "lab_report") -> Optional[Path]:
    """Pick mock file by detected document category without round-robin."""
    files = _load_mock_files()
    if not files:
        return None

    dt_lower = doc_type.lower()
    for f in files:
        if dt_lower in f.name.lower():
            return f
    # Fallback to lab report or first available
    for f in files:
        if "lab" in f.name.lower():
            return f
    return files[0] if files else None


class MockAIClient:
    async def extract(
        self,
        file_bytes: bytes,
        filename_hint: str = "",
        lang: str = "en",
    ) -> dict:
        if len(file_bytes) == 0:
            return {
                "record_id": str(uuid.uuid4()),
                "status": "REJECTED",
                "document_type": "NON_MEDICAL",
                "doc_type": "non_medical",
                "accepted": False,
                "reason_codes": ["EMPTY_FILE"],
                "error": {
                    "code": "EMPTY_FILE",
                    "message": "Uploaded file is empty.",
                },
                "tests": [],
                "medicines": [],
                "diagnoses": [],
            }

        # Try executing full content-based validation via ai_engine
        try:
            repo_root = AI_PROJECT_ROOT
            if str(repo_root) not in sys.path:
                sys.path.append(str(repo_root))
            from ai_engine import extract_record

            # Sniff mime and suffix from magic bytes
            if file_bytes.startswith(b"%PDF-"):
                suffix, mime = ".pdf", "application/pdf"
            elif file_bytes.startswith(b"\xff\xd8"):
                suffix, mime = ".jpg", "image/jpeg"
            elif file_bytes.startswith(b"\x89PNG"):
                suffix, mime = ".png", "image/png"
            elif file_bytes.startswith(b"RIFF") and b"WEBP" in file_bytes[:16]:
                suffix, mime = ".webp", "image/webp"
            elif file_bytes.startswith((b"II*\x00", b"MM\x00*")):
                suffix, mime = ".tiff", "image/tiff"
            else:
                ext = Path(filename_hint).suffix.lower() if filename_hint else ".pdf"
                suffix = ext if ext in {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"} else ".pdf"
                mime = mimetypes.guess_type("document" + suffix)[0] or "application/pdf"

            with tempfile.TemporaryDirectory(prefix="health-mock-") as temp:
                safe_stem = Path(filename_hint).stem if filename_hint else "document"
                path = Path(temp) / f"{safe_stem}{suffix}"
                path.write_bytes(file_bytes)

                prev_mode = os.environ.get("USE_MOCK_AI")
                try:
                    os.environ["USE_MOCK_AI"] = "true"
                    res = extract_record(str(path), mime, lang_hint=lang)
                    if isinstance(res, dict):
                        res["source"] = "mock"
                        return res
                finally:
                    if prev_mode is not None:
                        os.environ["USE_MOCK_AI"] = prev_mode
                    else:
                        os.environ.pop("USE_MOCK_AI", None)
        except Exception as exc:
            logger.debug("MockAIClient direct engine extraction skipped: %s", exc)

        # Fallback template loading if engine unavailable
        mock_file = _pick_mock_file("lab_report")
        if mock_file and mock_file.exists():
            try:
                data = json.loads(mock_file.read_text(encoding="utf-8"))
                data["record_id"] = str(uuid.uuid4())
                data["status"] = "ACCEPTED"
                data["accepted"] = True
                data["source"] = "mock"
                data.setdefault("language", lang or "en")
                return data
            except Exception as exc:
                logger.warning("Could not read mock file: %s", type(exc).__name__)

        # Absolute fallback
        return {
            "record_id": str(uuid.uuid4()),
            "status": "ACCEPTED",
            "accepted": True,
            "doc_type": "lab_report",
            "doc_date": "2024-01-01",
            "source": "mock",
            "language": lang or "en",
            "summary": "Mock extraction (no mock file found).",
            "tests": [],
            "medicines": [],
            "diagnoses": [],
        }


# ---------------------------------------------------------------------------
# Real AI Client (wraps Person 1's extract_record)
# ---------------------------------------------------------------------------
class RealAIClient:
    def __init__(self):
        self._extract_fn = None
        self._load_error: Optional[str] = None
        self._try_load()

    def _try_load(self):
        """Try to import ai_engine.extract_record at construction time."""
        repo_root = AI_PROJECT_ROOT
        if str(repo_root) not in sys.path:
            sys.path.append(str(repo_root))
        try:
            from ai_engine import extract_record  # type: ignore
            self._extract_fn = extract_record
            logger.info("ai_engine.extract_record loaded successfully.")
        except ImportError as exc:
            self._load_error = str(exc)
            logger.warning("ai_engine not available: %s", type(exc).__name__)

    async def extract(
        self,
        file_bytes: bytes,
        filename_hint: str = "",
        lang: str = "en",
    ) -> dict:
        settings = get_settings()
        if self._extract_fn is None:
            if settings.allow_mock_fallback:
                logger.info("ai_engine not available, using mock AI client fallback.")
                return await MockAIClient().extract(file_bytes, filename_hint, lang)
            raise RuntimeError(
                f"ai_engine.extract_record is not available: {self._load_error}"
            )

        loop = asyncio.get_event_loop()

        def _call():
            try:
                # Sniff true content format from magic bytes so filename never causes decoding errors
                if file_bytes.startswith(b"%PDF-"):
                    suffix, mime = ".pdf", "application/pdf"
                elif file_bytes.startswith(b"\xff\xd8"):
                    suffix, mime = ".jpg", "image/jpeg"
                elif file_bytes.startswith(b"\x89PNG"):
                    suffix, mime = ".png", "image/png"
                elif file_bytes.startswith(b"RIFF") and b"WEBP" in file_bytes[:16]:
                    suffix, mime = ".webp", "image/webp"
                elif file_bytes.startswith((b"II*\x00", b"MM\x00*")):
                    suffix, mime = ".tiff", "image/tiff"
                else:
                    ext = Path(filename_hint).suffix.lower() if filename_hint else ".pdf"
                    suffix = ext if ext in {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"} else ".pdf"
                    mime = mimetypes.guess_type("document" + suffix)[0] or "application/pdf"

                with tempfile.TemporaryDirectory(prefix="health-extract-") as temp:
                    safe_stem = Path(filename_hint).stem if filename_hint else "document"
                    path = Path(temp) / f"{safe_stem}{suffix}"
                    path.write_bytes(file_bytes)
                    result = self._extract_fn(str(path), mime, lang_hint=lang)
                if isinstance(result, dict):
                    result["source"] = result.get("source") or "ai"
                    return result
                if hasattr(result, "dict"):
                    return result.dict()
                if hasattr(result, "__dict__"):
                    return dict(result.__dict__)
                return dict(result)
            except Exception as exc:
                raise RuntimeError(f"AI extraction failed: {type(exc).__name__}") from exc

        try:
            res = await asyncio.wait_for(
                loop.run_in_executor(None, _call),
                timeout=settings.ai_timeout_seconds,
            )
            # Never fallback to mock if the AI engine deliberately rejected a non-medical document!
            is_rejected = (
                res.get("status") == "REJECTED"
                or res.get("accepted") is False
                or str(res.get("document_type", "")).upper() == "NON_MEDICAL"
                or str(res.get("doc_type", "")).lower() == "non_medical"
            )
            if is_rejected:
                return res

            if res.get("error"):
                logger.warning("AI extraction returned error: %s", res.get("error"))
                return res
            return res
        except Exception as exc:
            logger.error("AI extraction raised exception: %s", exc)
            repo_root = AI_PROJECT_ROOT
            if str(repo_root) not in sys.path:
                sys.path.append(str(repo_root))
            from ai_engine.models import make_error_record
            return make_error_record(
                "EXTRACTION_FAILED",
                f"Document processing failed: {type(exc).__name__}",
                reason_codes=["EXTRACTION_FAILED"],
            )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def get_ai_client() -> AIClient:
    settings = get_settings()
    if settings.use_mock_ai:
        return MockAIClient()
    real = RealAIClient()
    if real._extract_fn is not None:
        return real
    return MockAIClient()


_AI_CLIENT: Optional[AIClient] = None


def get_cached_ai_client() -> AIClient:
    """Return a module-level cached AI client (created once at startup)."""
    global _AI_CLIENT
    if _AI_CLIENT is None:
        _AI_CLIENT = get_ai_client()
    return _AI_CLIENT
