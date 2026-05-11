from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def ocr_png_bytes(png_bytes: bytes) -> tuple[str, str | None]:
    """
    OCR PNG image → text. Uses OpenCV preprocess + pytesseract when available.
    Returns (text, error_reason_or_none).
    """
    try:
        import cv2  # type: ignore[import-untyped]
    except ImportError:
        return "", "opencv_not_installed"

    arr = np.frombuffer(png_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return "", "decode_failed"

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=1.15, fy=1.15, interpolation=cv2.INTER_CUBIC)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    try:
        import pytesseract  # type: ignore[import-untyped]
    except ImportError:
        return "", "pytesseract_not_installed"

    try:
        text = pytesseract.image_to_string(th, config="--psm 3")
    except Exception as e:
        logger.info("tesseract OCR failed (install tesseract binary?): %s", e)
        return "", f"tesseract_failed:{e!s}"

    return (text or "").strip(), None


def ocr_stub(_png_bytes: bytes) -> tuple[str, str | None]:
    return "", "private_or_stub_image"
