import fitz
import pytest

from app.services.resume_parser import ResumeParsingError, extract_text


def _make_pdf_bytes(text: str) -> bytes:
    """Build a minimal in-memory PDF with the given text, for testing without fixture files."""
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    pdf_bytes = document.tobytes()
    document.close()
    return pdf_bytes


def test_extract_text_from_valid_pdf():
    pdf_bytes = _make_pdf_bytes("Python FastAPI Developer")
    text = extract_text(pdf_bytes)
    assert "Python" in text
    assert "FastAPI" in text


def test_empty_bytes_raises():
    with pytest.raises(ResumeParsingError):
        extract_text(b"")


def test_corrupt_pdf_raises():
    with pytest.raises(ResumeParsingError):
        extract_text(b"not a real pdf")


def test_blank_page_raises_no_text_error():
    document = fitz.open()
    document.new_page()  # page with no text at all
    pdf_bytes = document.tobytes()
    document.close()
    with pytest.raises(ResumeParsingError):
        extract_text(pdf_bytes)
