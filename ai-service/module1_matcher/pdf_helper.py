"""
PDF and Document Text Extractor for Module 1.
Extracts clean plain text from raw PDF bytes or uploaded files in-memory.
"""

import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import pypdf
    PYPDF_AVAILABLE = True
except ImportError:
    pypdf = None
    PYPDF_AVAILABLE = False


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """
    Extract text content from raw PDF bytes using pypdf.
    """
    if not PYPDF_AVAILABLE:
        logger.warning("[pdf_helper] pypdf is not installed. Returning empty text.")
        return ""

    if not pdf_bytes:
        return ""

    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        pages_text = []
        for idx, page in enumerate(reader.pages):
            txt = page.extract_text()
            if txt and txt.strip():
                pages_text.append(txt.strip())
        return "\n\n".join(pages_text).strip()
    except Exception as e:
        logger.error(f"[pdf_helper] Error extracting text from PDF bytes: {e}")
        return ""


def extract_document_text(
    file_bytes: Optional[bytes] = None,
    filename: Optional[str] = None,
    fallback_text: Optional[str] = None,
) -> str:
    """
    Determine if input is a PDF or raw text and return normalized plain text.
    """
    if file_bytes and len(file_bytes) > 0:
        is_pdf = (filename and filename.lower().endswith(".pdf")) or file_bytes.startswith(b"%PDF")
        if is_pdf:
            extracted = extract_text_from_pdf_bytes(file_bytes)
            if extracted:
                return extracted

        # If not PDF or PDF extraction returned empty, try utf-8 decode
        try:
            return file_bytes.decode("utf-8", errors="ignore").strip()
        except Exception:
            pass

    return (fallback_text or "").strip()
