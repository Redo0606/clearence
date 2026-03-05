"""PDF text extraction via pypdf. Raises PDFExtractionError for encrypted or corrupt PDFs."""

import logging
from io import BytesIO

from pypdf import PdfReader

logger = logging.getLogger(__name__)


class PDFExtractionError(Exception):
    """Raised when PDF text extraction fails."""

    pass


def extract_text_from_pdf(content: bytes) -> str:
    """
    Extract text from PDF bytes.
    Raises PDFExtractionError for encrypted, empty, or corrupt PDFs.
    """
    logger.debug("[PDF] Starting extraction | input_bytes=%d", len(content))
    if not content or len(content) == 0:
        raise PDFExtractionError("Empty PDF content")
    try:
        reader = PdfReader(BytesIO(content))
        num_pages = len(reader.pages)
        logger.debug("[PDF] PdfReader created | pages=%d | encrypted=%s", num_pages, reader.is_encrypted)
        if reader.is_encrypted:
            raise PDFExtractionError("Encrypted PDFs are not supported")
        text_parts: list[str] = []
        for i, page in enumerate(reader.pages):
            try:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
                    logger.debug("[PDF] Page %d/%d extracted | chars=%d", i + 1, num_pages, len(t))
            except Exception as e:
                raise PDFExtractionError(f"Failed to extract text from a page: {e}") from e
        result = "\n\n".join(text_parts).strip()
        logger.debug("[PDF] Extraction complete | total_chars=%d | pages_with_text=%d", len(result), len(text_parts))
        if not result:
            raise PDFExtractionError("No text could be extracted from the PDF")
        return result
    except PDFExtractionError:
        raise
    except Exception as e:
        raise PDFExtractionError(f"Failed to read PDF: {e}") from e
