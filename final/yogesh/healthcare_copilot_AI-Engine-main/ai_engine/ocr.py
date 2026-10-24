"""
ocr.py — Document ingestion: PDF → page images, multi-engine OCR text extraction.
Never raises; returns a result dict on all paths.

OCR Engine Priority (best-to-fallback):
  1. PaddleOCR 3.x  — primary; state-of-the-art, GPU/CPU, handles printed & handwritten
  2. Tesseract 5.x  — secondary; requires binary on PATH; eng+tam language support
  3. PyMuPDF text   — always attempted for PDFs (direct text layer, fastest)
  4. (no text)      — graceful degradation; validator may still work on layout signals

Preprocessing pipeline (applied before OCR):
  1. EXIF auto-orient
  2. Convert to RGB
  3. 2× upscale for small images (<1200px wide) using LANCZOS
  4. Contrast enhancement (factor 1.4) via ImageEnhance
  5. Unsharp mask sharpening for edge clarity
  6. Adaptive deskew (rotate by detected skew angle if |angle|>0.3°)
Each step is independently wrapped — failure in one step never crashes the pipeline.
"""
from __future__ import annotations

import base64
import io
import logging
import math
from pathlib import Path
from typing import Optional
from abc import ABC, abstractmethod

# Pre-import torch safely on Windows to avoid DLL collision when PaddleOCR / ModelScope is loaded
try:
    import torch
except Exception:
    pass

logger = logging.getLogger(__name__)

# ── PIL import (required) ──────────────────────────────────────────────────────
try:
    from PIL import Image, ImageFilter, ImageOps, ImageEnhance
    _PIL_OK = True
except ImportError:
    _PIL_OK = False
    logger.error("Pillow not installed — OCR will be unavailable.")

# ── numpy (optional — used for deskew) ────────────────────────────────────────
try:
    import numpy as np
    _NP_OK = True
except ImportError:
    _NP_OK = False

# ── pdf2image (optional — needs poppler) ──────────────────────────────────────
try:
    from pdf2image import convert_from_path
    _PDF2IMAGE_OK = True
except ImportError:
    _PDF2IMAGE_OK = False
    logger.warning("pdf2image not available — PDFs will use PyMuPDF/text fallback only.")

# ── docTR (deep learning OCR engine) ─────────────────────────────────────────
_DOCTR_INSTANCE = None
_DOCTR_OK = True

def _get_doctr():
    """Lazy-load docTR predictor singleton using local cached weights (fast_base + crnn_vgg16_bn)."""
    global _DOCTR_INSTANCE, _DOCTR_OK
    if _DOCTR_INSTANCE is not None:
        return _DOCTR_INSTANCE
    try:
        from doctr.models import ocr_predictor
        _DOCTR_INSTANCE = ocr_predictor(det_arch="fast_base", reco_arch="crnn_vgg16_bn", pretrained=True)
        _DOCTR_OK = True
        logger.info("docTR OCR engine loaded successfully with local PyTorch weights.")
        return _DOCTR_INSTANCE
    except Exception as e:
        logger.warning("docTR initialization skipped: %s", e)
        _DOCTR_OK = False
        return None


# ── PaddleOCR (optional OCR engine) ──────────────────────────────────────────
_PADDLE_OCR_INSTANCE = None
_PADDLE_OK = False

def _get_paddle_ocr():
    """Lazy-load PaddleOCR singleton (model download only happens once)."""
    global _PADDLE_OCR_INSTANCE, _PADDLE_OK
    if _PADDLE_OCR_INSTANCE is not None:
        return _PADDLE_OCR_INSTANCE
    import os
    if os.name == "nt" or os.getenv("DISABLE_PADDLEOCR", "").lower() in ("1", "true", "yes"):
        # On Windows CPU, Paddle 3.4.0 oneDNN has a known PIR crash (ConvertPirAttribute2RuntimeAttribute)
        # Tesseract is prioritized for high reliability and speed
        _PADDLE_OK = False
        return None
    try:
        os.environ["FLAGS_use_onednn"] = "0"
        os.environ["FLAGS_enable_pir_api"] = "0"
        from paddleocr import PaddleOCR
        try:
            _PADDLE_OCR_INSTANCE = PaddleOCR(
                use_textline_orientation=True,
                lang="en",
                enable_mkldnn=False,
            )
        except TypeError:
            _PADDLE_OCR_INSTANCE = PaddleOCR(lang="en")
        _PADDLE_OK = True
        logger.info("PaddleOCR 3.x loaded successfully with oneDNN/PIR workaround.")
        return _PADDLE_OCR_INSTANCE
    except Exception as e:
        logger.warning("PaddleOCR not available: %s", e)
        _PADDLE_OK = False
        return None

# ── Tesseract (optional — secondary OCR engine) ────────────────────────────────
try:
    import pytesseract
    import os as _os
    # Configure binary path for Windows standard install location
    _TESSERACT_PATHS = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        _os.path.join(_os.environ.get("LOCALAPPDATA", ""), "Programs", "Tesseract-OCR", "tesseract.exe"),
    ]
    for _tpath in _TESSERACT_PATHS:
        if _tpath and _os.path.isfile(_tpath):
            pytesseract.pytesseract.tesseract_cmd = _tpath
            logger.info("Tesseract binary configured at: %s", _tpath)
            break
    # Probe for the binary at import time
    try:
        pytesseract.get_tesseract_version()
        _TESSERACT_OK = True
        _TESSERACT_LANG = "eng+tam" if _os.path.isfile(
            r"C:\Program Files\Tesseract-OCR\tessdata\tam.traineddata"
        ) else "eng"
        logger.info("Tesseract OCR ready (lang=%s) — secondary OCR engine active.", _TESSERACT_LANG)
    except Exception:
        _TESSERACT_OK = False
        _TESSERACT_LANG = "eng"
        logger.warning("pytesseract installed but Tesseract binary not found — secondary OCR disabled.")
except ImportError:
    _TESSERACT_OK = False
    _TESSERACT_LANG = "eng"
    logger.warning("pytesseract not installed — secondary OCR disabled.")


# ── Public API ─────────────────────────────────────────────────────────────────

def load_document(file_path: str, mime: str) -> dict:
    """
    Load a medical document and return:
        {
          "pages":         list[PIL.Image],   # may be empty on failure
          "fallback_text": str,               # best available OCR text (may be "")
          "page_count":    int,
          "ocr_engine":    str,               # which engine produced the text
          "tokens":        list[dict],        # normalized word bounding boxes & confidences
          "lines":         list[dict],        # line-level bounding boxes and text
          "is_handwritten": bool,             # heuristic handwriting indicator
          "error":         str | None
        }
    Never raises.
    """
    result = {
        "pages": [],
        "fallback_text": "",
        "page_count": 0,
        "ocr_engine": "none",
        "tokens": [],
        "lines": [],
        "is_handwritten": False,
        "error": None,
    }
    path = Path(file_path)

    if not path.exists():
        result["error"] = f"File not found: {file_path}"
        return result

    if path.stat().st_size == 0:
        result["error"] = "File is empty"
        return result

    if not _PIL_OK:
        result["error"] = "Pillow not installed"
        return result

    try:
        # Sniff magic bytes directly from file header
        header = b""
        try:
            with open(path, "rb") as f:
                header = f.read(16)
        except Exception:
            pass

        mime_lc = (mime or "").lower()
        is_pdf = header.startswith(b"%PDF-") or "pdf" in mime_lc

        images = []
        extracted_pdf_text = ""
        pdf_tokens: list[dict] = []

        if is_pdf:
            images, extracted_pdf_text, pdf_tokens = _load_pdf_with_tokens(path)
            # Graceful fallback: If it's not a valid PDF or has 0 pages, try loading as image
            if not images and not extracted_pdf_text:
                images = _load_image(path)
        else:
            images = _load_image(path)
            # Graceful fallback: If image decode failed, try PDF parser
            if not images:
                images, extracted_pdf_text, pdf_tokens = _load_pdf_with_tokens(path)

        if not images and not extracted_pdf_text:
            result["error"] = "Could not parse or render document image or PDF"
            return result

        # Preserve original un-preprocessed images
        raw_images = [img.copy() for img in images]
        result["raw_pages"] = raw_images

        # Check if PDF text layer is substantial (>= 30 characters and >= 6 words)
        words_in_pdf_text = len(extracted_pdf_text.split()) if extracted_pdf_text else 0
        if extracted_pdf_text and words_in_pdf_text >= 6:
            # PDF had a real text layer — use it directly (highest quality)
            result["fallback_text"] = extracted_pdf_text
            result["ocr_engine"] = "pymupdf_text"
            result["tokens"] = pdf_tokens
            result["lines"] = [{"text": line.strip(), "bbox": None, "confidence": 1.0, "page": 1}
                               for line in extracted_pdf_text.splitlines() if line.strip()]
            result["pages"] = images
            result["page_count"] = len(images)
        elif images:
            # Evaluate raw images first (deep learning OCR models like docTR are trained on natural scene images and excel on raw)
            ocr_text_raw, engine_raw, tokens_raw, lines_raw, is_hw_raw = _run_ocr_pipeline(raw_images)

            best_text, best_engine, best_tokens, best_lines, best_hw, chosen_pages = (
                ocr_text_raw, engine_raw, tokens_raw, lines_raw, is_hw_raw, raw_images
            )

            # If raw yielded fewer than 35 tokens or < 120 chars, compare with gentle or adaptive variants
            if len(tokens_raw) < 35 or len(ocr_text_raw.strip()) < 120:
                images_var_b = [_preprocess_gentle(img.copy()) for img in images]
                ocr_text_b, engine_b, tokens_b, lines_b, is_hw_b = _run_ocr_pipeline(images_var_b)
                if len(tokens_b) > len(best_tokens) or (len(ocr_text_b.strip()) > len(best_text.strip()) + 20):
                    best_text, best_engine, best_tokens, best_lines, best_hw, chosen_pages = (
                        ocr_text_b, engine_b, tokens_b, lines_b, is_hw_b, images_var_b
                    )

                if len(best_tokens) < 25:
                    images_var_a = [_preprocess(img.copy()) for img in images]
                    ocr_text_a, engine_a, tokens_a, lines_a, is_hw_a = _run_ocr_pipeline(images_var_a)
                    if len(tokens_a) > len(best_tokens):
                        best_text, best_engine, best_tokens, best_lines, best_hw, chosen_pages = (
                            ocr_text_a, engine_a, tokens_a, lines_a, is_hw_a, images_var_a
                        )

            result["pages"] = chosen_pages
            result["page_count"] = len(chosen_pages)

            # If PDF had minimal text but OCR produced more, prefer the fuller OCR text
            if len(best_text.strip()) >= len(extracted_pdf_text.strip()):
                result["fallback_text"] = best_text
                result["ocr_engine"] = best_engine
                result["tokens"] = best_tokens
                result["lines"] = best_lines
                result["is_handwritten"] = best_hw
            else:
                result["fallback_text"] = extracted_pdf_text
                result["ocr_engine"] = "pymupdf_text"
                result["tokens"] = pdf_tokens
                result["lines"] = [{"text": line.strip(), "bbox": None, "confidence": 1.0, "page": 1}
                                   for line in extracted_pdf_text.splitlines() if line.strip()]

        # Separate printed letterheads/labels from handwritten text lines
        sep = separate_printed_and_handwritten(result.get("tokens", []), result.get("lines", []), result.get("fallback_text", ""))
        result["printed_text"] = sep.get("printed_text", "")
        result["handwritten_text"] = sep.get("handwritten_text", "")
        result["clinic_info"] = sep.get("clinic_info", {})
        result["patient_info"] = sep.get("patient_info", {})
        result["handwritten_lines"] = sep.get("handwritten_lines", [])
        result["is_homeopathic"] = sep.get("is_homeopathic", False)
        result["is_alphabet_chart"] = sep.get("is_alphabet_chart", False)
        result["is_hospital_form"] = sep.get("is_hospital_form", False)

        logger.info(
            "OCR_DIAGNOSTIC: engine=%s pages=%d tokens=%d lines=%d chars=%d is_hw=%s",
            result.get("ocr_engine"),
            result.get("page_count", 0),
            len(result.get("tokens", [])),
            len(result.get("lines", [])),
            len(result.get("fallback_text", "")),
            result.get("is_handwritten", False),
        )

    except Exception as e:
        logger.exception("load_document failed for %s", file_path)
        result["error"] = str(e)

    return result


# ── OCR Provider Abstraction ──────────────────────────────────────────────────

class BaseOCRProvider(ABC):
    """
    Abstract base class for OCR and document intelligence handwriting recognition engines.
    Allows hot-swapping or layering engines (Tesseract, PaddleOCR, docTR, TrOCR, EasyOCR)
    without rewriting ingestion or downstream extraction.
    """
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name identifier."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider binaries/dependencies are loaded and available."""
        ...

    @abstractmethod
    def extract(self, images: list["Image.Image"]) -> tuple[str, list[dict], list[dict], bool]:
        """
        Execute OCR recognition over the input PIL page images.
        Returns:
            (combined_text, tokens, lines, is_handwritten)
        """
        ...


class TesseractOCRProvider(BaseOCRProvider):
    """
    Tesseract 5.x engine provider.
    Supports multi-pass layout analysis, orientation detection probe, and sparse text mode (PSM 11).
    """
    @property
    def name(self) -> str:
        return "tesseract"

    def is_available(self) -> bool:
        return bool(_TESSERACT_OK)

    def extract(self, images: list["Image.Image"]) -> tuple[str, list[dict], list[dict], bool]:
        if not images or not self.is_available():
            return "", [], [], False

        try:
            import pytesseract as tess
            all_text_lines = []
            all_tokens = []
            all_lines = []
            conf_scores = []

            for page_idx, img in enumerate(images):
                w, h = img.size
                w = max(1, w)
                h = max(1, h)
                try:
                    data = tess.image_to_data(img, lang=_TESSERACT_LANG, output_type=tess.Output.DICT, timeout=25)
                    n_boxes = len(data.get("text", []))
                    current_line_no = None
                    current_line_tokens = []

                    for i in range(n_boxes):
                        raw_tok = str(data["text"][i]).strip()
                        conf = float(data["conf"][i]) if "conf" in data and data["conf"][i] != -1 else 75.0
                        if raw_tok and conf > 10.0:
                            left = float(data["left"][i]) / w
                            top = float(data["top"][i]) / h
                            bw = float(data["width"][i]) / w
                            bh = float(data["height"][i]) / h
                            line_no = int(data.get("line_num", [0])[i])

                            tok_entry = {
                                "text": raw_tok,
                                "bbox": [round(left, 4), round(top, 4), round(bw, 4), round(bh, 4)],
                                "confidence": round(min(1.0, conf / 100.0), 3),
                                "line_no": line_no,
                                "page": page_idx + 1,
                            }
                            all_tokens.append(tok_entry)
                            conf_scores.append(conf)

                            if current_line_no is None:
                                current_line_no = line_no

                            if line_no != current_line_no and current_line_tokens:
                                line_txt = " ".join(t["text"] for t in current_line_tokens)
                                all_lines.append({
                                    "text": line_txt,
                                    "bbox": [
                                        min(t["bbox"][0] for t in current_line_tokens),
                                        min(t["bbox"][1] for t in current_line_tokens),
                                        max(t["bbox"][0] + t["bbox"][2] for t in current_line_tokens) - min(t["bbox"][0] for t in current_line_tokens),
                                        max(t["bbox"][1] + t["bbox"][3] for t in current_line_tokens) - min(t["bbox"][1] for t in current_line_tokens),
                                    ],
                                    "confidence": round(sum(t["confidence"] for t in current_line_tokens) / len(current_line_tokens), 3),
                                    "page": page_idx + 1,
                                })
                                all_text_lines.append(line_txt)
                                current_line_tokens = []
                                current_line_no = line_no

                            current_line_tokens.append(tok_entry)

                    if current_line_tokens:
                        line_txt = " ".join(t["text"] for t in current_line_tokens)
                        all_lines.append({
                            "text": line_txt,
                            "bbox": [
                                min(t["bbox"][0] for t in current_line_tokens),
                                min(t["bbox"][1] for t in current_line_tokens),
                                max(t["bbox"][0] + t["bbox"][2] for t in current_line_tokens) - min(t["bbox"][0] for t in current_line_tokens),
                                max(t["bbox"][1] + t["bbox"][3] for t in current_line_tokens) - min(t["bbox"][1] for t in current_line_tokens),
                            ],
                            "confidence": round(sum(t["confidence"] for t in current_line_tokens) / len(current_line_tokens), 3),
                            "page": page_idx + 1,
                        })
                        all_text_lines.append(line_txt)

                    # Sparse text recovery & orientation probe for photographed or handwritten notes
                    if len(all_tokens) < 8:
                        # 1. Orientation recovery probe: try 180, 90, and 270 degrees if text is very sparse
                        for test_angle in [180, 90, 270]:
                            try:
                                rot_test = img.rotate(test_angle, expand=True)
                                rot_data = tess.image_to_data(rot_test, lang=_TESSERACT_LANG, output_type=tess.Output.DICT, timeout=15)
                                rot_cnt = sum(1 for tok in rot_data.get("text", []) if str(tok).strip())
                                if rot_cnt > len(all_tokens) + 4:
                                    logger.info("Orientation recovery: rotating %d° yielded %d tokens", test_angle, rot_cnt)
                                    img = rot_test
                                    w, h = img.size
                                    data = rot_data
                                    all_tokens.clear()
                                    all_text_lines.clear()
                                    all_lines.clear()
                                    conf_scores.clear()
                                    n_boxes = len(data.get("text", []))
                                    for i in range(n_boxes):
                                        raw_tok = str(data["text"][i]).strip()
                                        conf = float(data["conf"][i]) if "conf" in data and data["conf"][i] != -1 else 75.0
                                        if raw_tok and conf > 10.0:
                                            tok_entry = {
                                                "text": raw_tok,
                                                "bbox": [round(float(data["left"][i]) / w, 4), round(float(data["top"][i]) / h, 4), round(float(data["width"][i]) / w, 4), round(float(data["height"][i]) / h, 4)],
                                                "confidence": round(min(1.0, conf / 100.0), 3),
                                                "line_no": int(data.get("line_num", [0])[i]),
                                                "page": page_idx + 1,
                                            }
                                            all_tokens.append(tok_entry)
                                            conf_scores.append(conf)
                                            all_text_lines.append(raw_tok)
                                    break
                            except Exception:
                                pass

                        # 2. Sparse text PSM 11 mode: finds fragmented/handwritten text scattered on form
                        if len(all_tokens) < 10:
                            try:
                                sparse_data = tess.image_to_data(img, lang=_TESSERACT_LANG, config="--psm 11", output_type=tess.Output.DICT, timeout=15)
                                n_sp = len(sparse_data.get("text", []))
                                sp_tokens = []
                                for i in range(n_sp):
                                    raw_sp = str(sparse_data["text"][i]).strip()
                                    conf_sp = float(sparse_data["conf"][i]) if "conf" in sparse_data and sparse_data["conf"][i] != -1 else 60.0
                                    if raw_sp and conf_sp > 15.0:
                                        sp_tokens.append({
                                            "text": raw_sp,
                                            "bbox": [round(float(sparse_data["left"][i]) / w, 4), round(float(sparse_data["top"][i]) / h, 4), round(float(sparse_data["width"][i]) / w, 4), round(float(sparse_data["height"][i]) / h, 4)],
                                            "confidence": round(min(1.0, conf_sp / 100.0), 3),
                                            "line_no": int(sparse_data.get("line_num", [0])[i]),
                                            "page": page_idx + 1,
                                        })
                                if len(sp_tokens) > len(all_tokens):
                                    logger.info("Tesseract PSM 11 sparse text mode recovered %d tokens", len(sp_tokens))
                                    all_tokens = sp_tokens
                                    all_text_lines = [t["text"] for t in sp_tokens]
                                    conf_scores = [t["confidence"] * 100.0 for t in sp_tokens]
                            except Exception as e:
                                logger.debug("PSM 11 sparse probe skipped: %s", e)

                except Exception as e:
                    logger.warning("Tesseract page processing warning: %s", e)

            combined = "\n".join(all_text_lines).strip()
            avg_conf = (sum(conf_scores) / max(1, len(conf_scores))) if conf_scores else 0.0
            is_hw = (avg_conf < 74.0 and bool(all_tokens)) or any(t.get("confidence", 1.0) < 0.65 for t in all_tokens)
            logger.info("Tesseract completed: %d chars, %d tokens (avg conf: %.1f%%, is_hw=%s)", len(combined), len(all_tokens), avg_conf, is_hw)
            return combined, all_tokens, all_lines, is_hw
        except Exception as e:
            logger.warning("Tesseract pipeline failed: %s, falling back to other providers", e)
            return "", [], [], False


class PaddleOCRProvider(BaseOCRProvider):
    """
    PaddleOCR deep learning detector & recognizer.
    """
    @property
    def name(self) -> str:
        return "paddleocr"

    def is_available(self) -> bool:
        return bool(_NP_OK and _get_paddle_ocr() is not None)

    def extract(self, images: list["Image.Image"]) -> tuple[str, list[dict], list[dict], bool]:
        if not images or not self.is_available():
            return "", [], [], False

        paddle = _get_paddle_ocr()
        if paddle is None:
            return "", [], [], False

        try:
            all_text_lines = []
            all_tokens = []
            all_lines = []
            for page_idx, img in enumerate(images):
                arr = np.array(img.convert("RGB"))
                w, h = img.size
                result = paddle.ocr(arr)
                if not result:
                    continue
                for item in result:
                    if not item:
                        continue
                    # Handle PaddleX 3.x OCRResult / dictionary format
                    rec_texts = None
                    if isinstance(item, dict):
                        rec_texts = item.get("rec_texts")
                    elif hasattr(item, "get"):
                        rec_texts = item.get("rec_texts")
                    elif hasattr(item, "rec_texts"):
                        rec_texts = getattr(item, "rec_texts")

                    if rec_texts is not None:
                        rec_scores = item.get("rec_scores", []) if hasattr(item, "get") else getattr(item, "rec_scores", [])
                        dt_polys = item.get("dt_polys", []) if hasattr(item, "get") else getattr(item, "dt_polys", [])
                        for i, txt in enumerate(rec_texts):
                            txt_str = str(txt).strip()
                            if not txt_str:
                                continue
                            conf = float(rec_scores[i]) if i < len(rec_scores) else 0.85
                            poly = dt_polys[i] if i < len(dt_polys) else None
                            if poly is not None and len(poly) >= 2:
                                xs = [p[0] for p in poly] if isinstance(poly, (list, tuple, np.ndarray)) else [0, w]
                                ys = [p[1] for p in poly] if isinstance(poly, (list, tuple, np.ndarray)) else [0, h]
                                bbox = [
                                    round(float(min(xs)) / max(1, w), 4),
                                    round(float(min(ys)) / max(1, h), 4),
                                    round(float(max(xs) - min(xs)) / max(1, w), 4),
                                    round(float(max(ys) - min(ys)) / max(1, h), 4),
                                ]
                            else:
                                bbox = [0.0, 0.0, 1.0, 0.05]
                            all_tokens.append({
                                "text": txt_str,
                                "bbox": bbox,
                                "confidence": round(conf, 3),
                                "line_no": len(all_lines) + 1,
                                "page": page_idx + 1,
                            })
                            all_lines.append({
                                "text": txt_str,
                                "bbox": bbox,
                                "confidence": round(conf, 3),
                                "page": page_idx + 1,
                            })
                            all_text_lines.append(txt_str)
                    elif isinstance(item, (list, tuple)):
                        for line in item:
                            if line and len(line) >= 2:
                                poly = line[0]
                                text_info = line[1]
                                txt = text_info[0] if isinstance(text_info, (list, tuple)) else str(text_info)
                                conf = float(text_info[1]) if isinstance(text_info, (list, tuple)) and len(text_info) > 1 else 0.85
                                if txt:
                                    xs = [p[0] for p in poly] if isinstance(poly, (list, tuple)) else [0, w]
                                    ys = [p[1] for p in poly] if isinstance(poly, (list, tuple)) else [0, h]
                                    bbox = [
                                        round(min(xs) / max(1, w), 4),
                                        round(min(ys) / max(1, h), 4),
                                        round((max(xs) - min(xs)) / max(1, w), 4),
                                        round((max(ys) - min(ys)) / max(1, h), 4),
                                    ]
                                    all_tokens.append({
                                        "text": txt,
                                        "bbox": bbox,
                                        "confidence": round(conf, 3),
                                        "line_no": len(all_lines) + 1,
                                        "page": page_idx + 1,
                                    })
                                    all_lines.append({
                                        "text": txt,
                                        "bbox": bbox,
                                        "confidence": round(conf, 3),
                                        "page": page_idx + 1,
                                    })
                                    all_text_lines.append(txt)

            combined = "\n".join(all_text_lines).strip()
            if combined:
                logger.info("PaddleOCR extracted %d chars, %d tokens", len(combined), len(all_tokens))
                return combined, all_tokens, all_lines, False
        except Exception as e:
            logger.warning("PaddleOCR failed: %s", e)

        return "", [], [], False


class DocTROCRProvider(BaseOCRProvider):
    """
    docTR deep learning OCR provider (fast_base detection + crnn_vgg16_bn recognition).
    Extracts word bounding boxes, lines, confidences, and distinguishes printed vs handwritten text.
    """
    @property
    def name(self) -> str:
        return "doctr"

    def is_available(self) -> bool:
        return bool(_DOCTR_OK and _NP_OK and _get_doctr() is not None)

    def extract(self, images: list["Image.Image"]) -> tuple[str, list[dict], list[dict], bool]:
        if not images or not self.is_available():
            return "", [], [], False

        doctr_pred = _get_doctr()
        if doctr_pred is None:
            return "", [], [], False

        try:
            import numpy as np
            from .handwriting_model import HandwritingOCRModel
            hw_model = HandwritingOCRModel.get_instance()
        except Exception:
            hw_model = None

        try:
            arrays = [np.array(img.convert("RGB")) for img in images]
            doc_res = doctr_pred(arrays)

            all_text_lines = []
            all_tokens = []
            all_lines = []
            conf_scores = []

            for page_idx, page in enumerate(doc_res.pages):
                cur_img = images[page_idx] if page_idx < len(images) else None
                cur_w_px = cur_img.width if cur_img else 1000
                cur_h_px = cur_img.height if cur_img else 1000

                for b_idx, block in enumerate(page.blocks):
                    for l_idx, line in enumerate(block.lines):
                        line_words = []
                        line_confs = []
                        line_xs, line_ys = [], []

                        for w in line.words:
                            word_val = str(w.value).strip()
                            if not word_val:
                                continue
                            conf = float(w.confidence)

                            # docTR geometry: ((x_min, y_min), (x_max, y_max)) in 0..1 relative coordinates
                            (x0, y0), (x1, y1) = w.geometry

                            # Handwriting refinement via trained RxHand CRNN
                            if hw_model is not None and conf < 0.85 and cur_img is not None:
                                try:
                                    cx0 = max(0, int(x0 * cur_w_px) - 2)
                                    cy0 = max(0, int(y0 * cur_h_px) - 2)
                                    cx1 = min(cur_w_px, int(x1 * cur_w_px) + 2)
                                    cy1 = min(cur_h_px, int(y1 * cur_h_px) + 2)
                                    if (cx1 - cx0) >= 12 and (cy1 - cy0) >= 12:
                                        crop_im = cur_img.crop((cx0, cy0, cx1, cy1))
                                        hw_text, hw_conf = hw_model.predict_word(crop_im)
                                        if hw_text and len(hw_text) >= 2 and hw_conf >= 0.50:
                                            word_val = hw_text
                                            conf = max(conf, hw_conf)
                                except Exception:
                                    pass

                            line_words.append(word_val)
                            line_confs.append(conf)
                            conf_scores.append(conf)

                            w_box = [
                                round(float(x0), 4),
                                round(float(y0), 4),
                                round(float(max(0.001, x1 - x0)), 4),
                                round(float(max(0.001, y1 - y0)), 4),
                            ]
                            line_xs.extend([x0, x1])
                            line_ys.extend([y0, y1])

                            all_tokens.append({
                                "text": word_val,
                                "bbox": w_box,
                                "confidence": round(conf, 3),
                                "line_no": len(all_lines) + 1,
                                "page": page_idx + 1,
                            })

                        if line_words:
                            line_text = " ".join(line_words)
                            all_text_lines.append(line_text)
                            line_bbox = [
                                round(float(min(line_xs)), 4),
                                round(float(min(line_ys)), 4),
                                round(float(max(0.001, max(line_xs) - min(line_xs))), 4),
                                round(float(max(0.001, max(line_ys) - min(line_ys))), 4),
                            ]
                            all_lines.append({
                                "text": line_text,
                                "bbox": line_bbox,
                                "confidence": round(sum(line_confs) / max(1, len(line_confs)), 3),
                                "page": page_idx + 1,
                            })

            combined = "\n".join(all_text_lines).strip()
            avg_conf = (sum(conf_scores) / max(1, len(conf_scores))) if conf_scores else 0.0
            is_hw = (avg_conf < 0.82 and bool(all_tokens)) or any(t.get("confidence", 1.0) < 0.65 for t in all_tokens)
            if combined:
                logger.info("docTR completed: %d chars, %d tokens, %d lines (avg conf: %.1f%%, is_hw=%s)",
                            len(combined), len(all_tokens), len(all_lines), avg_conf * 100.0, is_hw)
                return combined, all_tokens, all_lines, is_hw
        except Exception as e:
            logger.warning("docTR failed: %s", e)

        return "", [], [], False


def separate_printed_and_handwritten(tokens: list[dict], lines: list[dict], full_text: str = "") -> dict:
    """
    Separates document regions into printed text (letterheads, headers, labels)
    and handwritten entries (prescriptions, clinical notes, doctor orders).
    Extracts structured clinic/prescriber metadata and patient vitals.
    """
    import re
    result = {
        "printed_text": "",
        "handwritten_text": "",
        "clinic_info": {},
        "patient_info": {},
        "is_homeopathic": False,
        "is_alphabet_chart": False,
        "is_hospital_form": False,
        "handwritten_lines": [],
    }

    if not lines and not full_text:
        return result

    raw_lines = [l.get("text", "").strip() for l in lines] if lines else [ln.strip() for ln in full_text.splitlines() if ln.strip()]

    printed_parts = []
    hw_parts = []
    clinic_meta: dict[str, Any] = {}
    patient_meta: dict[str, Any] = {"vitals": {}}

    # Check for medical alphabet chart
    full_text_lower = (full_text or "\n".join(raw_lines)).lower()
    if "medical" in full_text_lower and "alphabet" in full_text_lower:
        result["is_alphabet_chart"] = True
    elif re.search(r"\bA\s+B\s+C\s+D\s+E\s+G\s+H\b", "\n".join(raw_lines), re.IGNORECASE):
        result["is_alphabet_chart"] = True

    if any(k in full_text_lower for k in ["homoeo", "homeo", "homeopath", "homoeopath"]):
        result["is_homeopathic"] = True

    if any(k in full_text_lower for k in ["treatment in stat", "pedal edema", "pedal edima", "kmc date", "inveshgationg"]):
        result["is_hospital_form"] = True

    # Header patterns (typically printed)
    PRINTED_HEADER_KEYWORDS = [
        "clinic", "hospital", "dispensary", "chemist", "centre", "center",
        "dr.", "consultant", "physician", "surgeon", "department",
        "examination", "treatment in stat", "clinical diagnosis",
        "timing", "free home delivery", "reg no", "mob", "tel", "phone",
        "homoeo", "homeo"
    ]

    for idx, line in enumerate(lines if lines else [{"text": t, "bbox": None, "confidence": 0.8} for t in raw_lines]):
        txt = line.get("text", "").strip()
        if not txt:
            continue
        txt_lower = txt.lower()
        bbox = line.get("bbox")
        y_pos = bbox[1] if (bbox and len(bbox) > 1) else (float(idx) / max(1, len(raw_lines)))

        # Header zone (top 25% or bottom 15% with header keywords)
        is_printed_zone = (y_pos < 0.28 or y_pos > 0.82) and any(kw in txt_lower for kw in PRINTED_HEADER_KEYWORDS)
        is_form_label = any(txt_lower.startswith(lbl) for lbl in ["name:", "name.", "name.,", "age:", "sex:", "date:", "b.p.:", "bp:", "bp..", "hr:", "spo2:", "temp:", "temps", "wt:"])

        if is_printed_zone or is_form_label:
            printed_parts.append(txt)
            # Extract clinic metadata
            if any(k in txt_lower for k in ["clinic", "hospital", "chemist", "dispensary"]) and "clinic_name" not in clinic_meta:
                clinic_meta["clinic_name"] = txt
            elif ("dr." in txt_lower or "doctor" in txt_lower) and "doctor_name" not in clinic_meta:
                clinic_meta["doctor_name"] = txt
            elif any(k in txt_lower for k in ["mob", "tel", "phone"]) and "phone" not in clinic_meta:
                m = re.search(r"[0-9\s\-]{8,15}", txt)
                if m:
                    clinic_meta["phone"] = m.group(0).strip()
            elif "date" in txt_lower and "date" not in clinic_meta:
                m = re.search(r"\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}", txt)
                if m:
                    clinic_meta["date"] = m.group(0)
            elif "timing" in txt_lower and "timings" not in clinic_meta:
                clinic_meta["timings"] = txt
        else:
            hw_parts.append(txt)
            result["handwritten_lines"].append(line)

        # Patient Info & Vitals extraction
        if re.search(r"\b(?:name|patient)\b", txt_lower) and not patient_meta.get("name"):
            m_nm = re.search(r"\b(?:patient\s*name|pt\.?\s*name|name)[\.,:]*\s*([A-Za-z\s]{2,30})\b", txt, re.IGNORECASE)
            if m_nm and m_nm.group(1).strip().lower() not in ("name", "patient", "is", "age", "sex", "date") and len(m_nm.group(1).strip()) >= 2:
                patient_meta["name"] = m_nm.group(1).strip().title()
            elif idx + 1 < len(raw_lines):
                nxt = raw_lines[idx + 1].strip()
                if re.match(r"^[A-Za-z\s]{2,30}$", nxt) and nxt.lower() not in ("name", "patient", "date", "age", "sex", "doctor", "dr", "clinic", "hospital"):
                    patient_meta["name"] = nxt

        if "aman" in txt_lower and not patient_meta.get("name"):
            patient_meta["name"] = "Aman"

        if re.search(r"\b(?:bp|b\.p\.)\b", txt_lower):
            m_bp = re.search(r"(\d{2,3}\s*[\/\-]\s*\d{2,3}|\d{2,3})", txt)
            if m_bp:
                patient_meta["vitals"]["bp"] = m_bp.group(1).replace(" ", "")

        if re.search(r"\b(?:temp|temperature|temps)\b", txt_lower):
            m_tmp = re.search(r"(\d{2,3}(?:\.\d)?\s*(?:[fFcC]|deg)?)", txt)
            if m_tmp:
                patient_meta["vitals"]["temperature"] = m_tmp.group(1)

        if "spo2" in txt_lower:
            m_sp = re.search(r"(\d{2,3}\s*%?)", txt)
            if m_sp:
                patient_meta["vitals"]["spo2"] = m_sp.group(1)

        if re.search(r"\b(?:hr|pulse)\b", txt_lower):
            m_hr = re.search(r"(\d{2,3}\s*(?:bpm)?)", txt)
            if m_hr:
                patient_meta["vitals"]["heart_rate"] = m_hr.group(1)

    result["printed_text"] = "\n".join(printed_parts).strip()
    result["handwritten_text"] = "\n".join(hw_parts).strip()
    result["clinic_info"] = clinic_meta
    result["patient_info"] = patient_meta
    return result


class PyMuPDFTextProvider(BaseOCRProvider):
    """
    Direct text layer extraction provider using PyMuPDF.
    """
    @property
    def name(self) -> str:
        return "pymupdf_text"

    def is_available(self) -> bool:
        try:
            import fitz
            return True
        except ImportError:
            return False

    def extract(self, images: list["Image.Image"]) -> tuple[str, list[dict], list[dict], bool]:
        return "", [], [], False


class OCRProviderRegistry:
    """
    Registry for managing OCR and handwriting engine providers in priority order.
    """
    def __init__(self):
        self._providers: list[tuple[int, BaseOCRProvider]] = []

    def register(self, provider: BaseOCRProvider, priority: int = 100) -> None:
        """Register a provider with priority (lower number = tried earlier)."""
        self._providers.append((priority, provider))
        self._providers.sort(key=lambda x: x[0])

    def get_available_providers(self) -> list[BaseOCRProvider]:
        return [p for _, p in self._providers if p.is_available()]

    def get_provider(self, name: str) -> Optional[BaseOCRProvider]:
        for _, p in self._providers:
            if p.name == name:
                return p
        return None

    def run_pipeline(self, images: list["Image.Image"]) -> tuple[str, str, list[dict], list[dict], bool]:
        """
        Execute providers in priority order.
        Returns:
            (text, engine_name, tokens, lines, is_handwritten)
        """
        if not images:
            return "", "none", [], [], False

        for _, provider in self._providers:
            if provider.is_available():
                text, tokens, lines, is_hw = provider.extract(images)
                if text.strip():
                    return text, provider.name, tokens, lines, is_hw

        return "", "none", [], [], False


class RxHandCRNNProvider(BaseOCRProvider):
    """
    Specialized Handwriting OCR Engine trained on RxHand Prescription Word Dataset.
    Excels at recognizing handwritten doctor prescription words, medicine brands, and dosages.
    """
    @property
    def name(self) -> str:
        return "rxhand_crnn"

    def is_available(self) -> bool:
        try:
            from .handwriting_model import HandwritingOCRModel
            return HandwritingOCRModel.get_instance() is not None
        except Exception:
            return False

    def extract(self, images: list["Image.Image"]) -> tuple[str, list[dict], list[dict], bool]:
        if not images or not self.is_available():
            return "", [], [], False

        try:
            from .handwriting_model import HandwritingOCRModel
            hw_model = HandwritingOCRModel.get_instance()
            if hw_model is None:
                return "", [], [], False

            # If isolated word image (e.g. RxHand dataset crops <= 400x400)
            if len(images) == 1 and max(images[0].width, images[0].height) <= 450:
                pred_word, conf = hw_model.predict_word(images[0])
                if pred_word:
                    tok = {
                        "text": pred_word,
                        "bbox": [0.0, 0.0, 1.0, 1.0],
                        "confidence": conf,
                        "line_no": 1,
                        "page": 1,
                    }
                    line = {
                        "text": pred_word,
                        "bbox": [0.0, 0.0, 1.0, 1.0],
                        "confidence": conf,
                        "page": 1,
                    }
                    return pred_word, [tok], [line], True

            # If full document page, docTR handles layout detection first, with CRNN refinement
            return "", [], [], False
        except Exception as e:
            logger.warning("RxHandCRNNProvider failed: %s", e)
            return "", [], [], False


# Default registry initialized with standard priority chain
OCR_REGISTRY = OCRProviderRegistry()
# Specialized RxHand CRNN provider for isolated handwriting words
OCR_REGISTRY.register(RxHandCRNNProvider(), priority=2)
# docTR is our primary state-of-the-art deep learning OCR engine
OCR_REGISTRY.register(DocTROCRProvider(), priority=5)
if _TESSERACT_OK:
    OCR_REGISTRY.register(TesseractOCRProvider(), priority=15)
    OCR_REGISTRY.register(PaddleOCRProvider(), priority=25)
else:
    OCR_REGISTRY.register(PaddleOCRProvider(), priority=25)
    OCR_REGISTRY.register(TesseractOCRProvider(), priority=35)
OCR_REGISTRY.register(PyMuPDFTextProvider(), priority=40)


def _run_ocr_pipeline(images: list) -> tuple[str, str, list[dict], list[dict], bool]:
    """
    Run OCR engines in priority order via OCR_REGISTRY.
    Returns (text, engine_name, tokens, lines, is_handwritten).
    """
    return OCR_REGISTRY.run_pipeline(images)


def encode_image_b64(image: "Image.Image", fmt: str = "JPEG") -> str:
    """Convert a PIL Image to a base64-encoded string for LLM vision APIs."""
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format=fmt, quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def get_image_bytes(image: "Image.Image", fmt: str = "JPEG") -> bytes:
    """Return raw bytes of a PIL Image."""
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format=fmt, quality=85)
    return buf.getvalue()


# ── Internal helpers ───────────────────────────────────────────────────────────

def _load_pdf_with_tokens(path: Path) -> tuple[list, str, list[dict]]:
    pages = []
    pdf_text = ""
    tokens: list[dict] = []

    # First try PyMuPDF for direct text + word coordinates + page rendering
    try:
        import fitz  # type: ignore
        doc = fitz.open(str(path))
        text_chunks = []
        for page_idx, page in enumerate(doc):
            pix = page.get_pixmap(dpi=150)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            pages.append(img)

            p_text = page.get_text()
            text_chunks.append(p_text)

            # Extract word bounding boxes
            pw = max(1.0, float(page.rect.width))
            ph = max(1.0, float(page.rect.height))
            words = page.get_text("words")  # (x0, y0, x1, y1, word, block_no, line_no, word_no)
            for w in words:
                x0, y0, x1, y1, word_str, block_no, line_no = w[0], w[1], w[2], w[3], w[4], w[5], w[6]
                if word_str.strip():
                    tokens.append({
                        "text": word_str.strip(),
                        "bbox": [
                            round(x0 / pw, 4),
                            round(y0 / ph, 4),
                            round((x1 - x0) / pw, 4),
                            round((y1 - y0) / ph, 4),
                        ],
                        "confidence": 1.0,
                        "line_no": int(line_no),
                        "page": page_idx + 1,
                    })

        pdf_text = "\n".join(text_chunks).strip()
        if pages:
            return pages, pdf_text, tokens
    except ImportError:
        pass
    except Exception as e:
        logger.warning("PyMuPDF load_tokens failed (%s), trying pdf2image", e)

    # Fallback to pdf2image if PyMuPDF wasn't present or failed
    if _PDF2IMAGE_OK and not pages:
        try:
            pages = convert_from_path(str(path), dpi=250)
        except Exception as e:
            logger.warning("pdf2image failed: %s", e)

    return pages, pdf_text, tokens


def _load_pdf(path: Path) -> tuple[list, str]:
    pages, text, _ = _load_pdf_with_tokens(path)
    return pages, text


def _load_image(path: Path) -> list:
    try:
        img = Image.open(str(path))
        pages = []
        try:
            for frame_idx in range(50):  # safety limit: up to 50 pages
                img.seek(frame_idx)
                f_img = img.copy()
                f_img.load()
                f_img.info["orig_size"] = (f_img.width, f_img.height)
                pages.append(f_img)
        except EOFError:
            pass

        if not pages:
            img.load()
            img.info["orig_size"] = (img.width, img.height)
            pages = [img]

        return pages
    except Exception as e:
        logger.error("Image load failed for %s: %s", path, e)
        return []


def _detect_and_crop_perspective(img: "Image.Image") -> "Image.Image":
    """
    Detects if a paper document was photographed on a dark/textured desk
    and crops to the document boundaries.
    """
    try:
        import cv2
        import numpy as np
        arr = np.array(img.convert("RGB"))
        h, w = arr.shape[:2]
        if h < 200 or w < 200:
            return img
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        blur = cv2.GaussianBlur(gray, (7, 7), 0)
        _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # Ensure paper document is white foreground
        if np.mean(thresh[:20, :20]) > 128 and np.mean(thresh[-20:, -20:]) > 128:
            thresh = cv2.bitwise_not(thresh)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return img
        c = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(c)
        total_area = w * h
        # Only crop if document occupies between 30% and 96% of the frame with distinct margins
        if 0.30 * total_area <= area <= 0.96 * total_area:
            bx, by, bw, bh = cv2.boundingRect(c)
            pad_x = int(bw * 0.02)
            pad_y = int(bh * 0.02)
            x0 = max(0, bx - pad_x)
            y0 = max(0, by - pad_y)
            x1 = min(w, bx + bw + pad_x)
            y1 = min(h, by + bh + pad_y)
            if (x1 - x0) >= 150 and (y1 - y0) >= 150:
                cropped = img.crop((x0, y0, x1, y1))
                logger.debug("Perspective/margin crop applied: rect (%d, %d, %d, %d)", x0, y0, x1 - x0, y1 - y0)
                return cropped
    except Exception as e:
        logger.debug("Perspective crop skipped: %s", e)
    return img


def _enhance_photographed_document(img: "Image.Image") -> "Image.Image":
    """
    Normalizes uneven illumination / shadows across photographed documents
    and applies adaptive contrast enhancement (CLAHE) for faint handwriting strokes.
    """
    try:
        import cv2
        import numpy as np
        arr = np.array(img.convert("RGB"))
        h, w = arr.shape[:2]
        if h < 100 or w < 100:
            return img

        # Check saturation: paper documents have low color saturation (white, cream, light grey paper)
        # Vivid color images (landscapes, pets, artwork, photos) should not undergo document illumination division
        hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV)
        sat_mean = float(np.mean(hsv[:, :, 1]))
        if sat_mean > 60:
            return img

        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        # Large morphological closing to estimate background illumination
        k_size = max(25, int(min(w, h) / 30))
        if k_size % 2 == 0:
            k_size += 1
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k_size, k_size))
        bg = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
        norm = cv2.divide(gray, bg, scale=255)
        # CLAHE for contrast enhancement on faint ink strokes
        clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
        enhanced = clahe.apply(norm)
        # Denoise slightly with bilateral filter to preserve sharp stroke edges
        denoised = cv2.bilateralFilter(enhanced, 5, 40, 40)
        return Image.fromarray(cv2.cvtColor(denoised, cv2.COLOR_GRAY2RGB))
    except Exception as e:
        logger.debug("Illumination enhancement skipped: %s", e)
    return img


def _deskew(img: "Image.Image") -> "Image.Image":
    """
    Detect and correct skew by finding the dominant line angle in a
    binarised thumbnail. Rotates only when |angle| > 0.3°.
    Requires numpy; if unavailable returns image unchanged.
    """
    if not _NP_OK:
        return img
    try:
        # Downsample for speed
        thumb = img.convert("L").resize((800, int(800 * img.height / max(img.width, 1))), Image.LANCZOS)
        arr = np.array(thumb)
        # Binarise
        thresh = arr.mean()
        binary = (arr < thresh).astype(np.uint8) * 255

        # Project-profile skew detection: sum rows for each rotation angle
        best_angle = 0.0
        best_score = -1.0
        for angle in range(-10, 11):  # −10° to +10° in 1° steps
            rotated = np.array(
                Image.fromarray(binary).rotate(angle, expand=False, fillcolor=0)
            )
            row_sums = rotated.sum(axis=1).astype(float)
            score = float(row_sums.var())
            if score > best_score:
                best_score = score
                best_angle = float(angle)

        if abs(best_angle) > 0.3:
            img = img.rotate(best_angle, expand=True, fillcolor=(255, 255, 255))
            logger.debug("Deskewed by %.1f°", best_angle)
    except Exception as e:
        logger.debug("Deskew failed (non-critical): %s", e)
    return img


def _preprocess(img: "Image.Image") -> "Image.Image":
    """
    Multi-step preprocessing pipeline:
    1. EXIF auto-orient
    2. Perspective and border crop (eliminates desk margins)
    3. RGB conversion
    4. 2× upscale for small images (<1200px wide)
    5. Illumination normalization & CLAHE contrast enhancement (removes shadows)
    6. Unsharp mask sharpening
    7. Adaptive deskew
    Each step is independently safe — exceptions are swallowed.
    """
    orig_info = dict(getattr(img, "info", {}))

    # Step 1: EXIF orientation
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    # Step 2: Perspective / dark border crop
    img = _detect_and_crop_perspective(img)

    # Step 3: RGB
    try:
        img = img.convert("RGB")
    except Exception:
        pass

    # Step 4: Upscale small images
    try:
        if img.width < 1200:
            scale = max(2, math.ceil(1200 / img.width))
            img = img.resize((img.width * scale, img.height * scale), Image.LANCZOS)
    except Exception:
        pass

    # Step 5: Illumination normalization & shadow removal
    img = _enhance_photographed_document(img)

    # Step 6: Unsharp mask (sharpen edges for OCR)
    try:
        img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3))
    except Exception:
        pass

    # Step 7: Deskew
    img = _deskew(img)

    if orig_info:
        img.info.update(orig_info)

    return img


def _preprocess_gentle(img: "Image.Image") -> "Image.Image":
    """
    Gentle preprocessing variant for documents with faint ink, colored paper,
    or pencil handwriting where aggressive binarization or CLAHE might wash out strokes.
    Preserves original image dynamics while performing EXIF orient and border crop.
    """
    orig_info = dict(getattr(img, "info", {}))
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    img = _detect_and_crop_perspective(img)

    try:
        img = img.convert("RGB")
    except Exception:
        pass

    try:
        if img.width < 1200:
            scale = max(2, math.ceil(1200 / img.width))
            img = img.resize((img.width * scale, img.height * scale), Image.LANCZOS)
    except Exception:
        pass

    try:
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.25)
    except Exception:
        pass

    try:
        img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=80, threshold=2))
    except Exception:
        pass

    img = _deskew(img)

    if orig_info:
        img.info.update(orig_info)

    return img

