"""PDF text extraction via pdfminer.six. Raises PDFExtractionError for encrypted or corrupt PDFs.

Uses the same library as ontology_builder/pipeline/loader.py for consistent extraction
across PDF-to-OWL and full pipeline flows.
"""

import logging
from io import BytesIO

from pdfminer.high_level import extract_text as pdfminer_extract_text

logger = logging.getLogger(__name__)


class PDFExtractionError(Exception):
    """Raised when PDF text extraction fails."""

    pass


def extract_text_from_pdf(content: bytes) -> str:
    """Extract text from PDF bytes.

    Args:
        content: Raw PDF file bytes.

    Returns:
        Extracted text concatenated from all pages.

    Raises:
        PDFExtractionError: For encrypted, empty, or corrupt PDFs.
    """
    logger.debug("[PDF] Starting extraction | input_bytes=%d", len(content))
    if not content or len(content) == 0:
        raise PDFExtractionError("Empty PDF content")
    try:
        text = pdfminer_extract_text(BytesIO(content))
        result = (text or "").strip()
        logger.debug("[PDF] Extraction complete | total_chars=%d", len(result))
        if not result:
            raise PDFExtractionError("No text could be extracted from the PDF")
        return result
    except PDFExtractionError:
        raise
    except Exception as e:
        raise PDFExtractionError(f"Failed to read PDF: {e}") from e
