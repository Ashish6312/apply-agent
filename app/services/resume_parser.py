"""Deterministic PDF text extraction. Pure file handling - no LLM involved.

Kept as its own service so it is independently unit-testable and so the
agent node stays thin (it just calls this + the LLM extractor).
"""
import fitz  # PyMuPDF


class ResumeParsingError(Exception):
    """Raised when a PDF cannot be read or contains no extractable text."""


def extract_text(pdf_bytes: bytes) -> str:
    """Extract plain text from a resume PDF.

    Raises ResumeParsingError on corrupt files or PDFs with no text layer
    (e.g. a scanned image) so the caller can surface a clear error instead
    of silently continuing with an empty resume.
    """
    if not pdf_bytes:
        raise ResumeParsingError("Empty file provided.")

    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:  # PyMuPDF raises its own exception types
        raise ResumeParsingError(f"Could not open PDF: {exc}") from exc

    pages_text = [page.get_text() for page in document]
    document.close()

    full_text = "\n".join(pages_text).strip()
    if not full_text:
        raise ResumeParsingError(
            "No extractable text found in PDF. It may be a scanned image without a text layer."
        )
    return full_text
