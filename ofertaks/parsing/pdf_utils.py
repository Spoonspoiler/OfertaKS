"""PDF extraction helpers."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO


@dataclass(slots=True)
class PDFExtraction:
    text: str
    status: str
    pages: int
    error: str | None = None


def extract_text_from_pdf_bytes(content: bytes) -> PDFExtraction:
    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover - depends on packaging
        return PDFExtraction(text="", status="pypdf_unavailable", pages=0, error=str(exc))

    try:
        reader = PdfReader(BytesIO(content))
        parts: list[str] = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        text = "\n".join(part for part in parts if part.strip())
    except Exception as exc:
        return PDFExtraction(text="", status="failed", pages=0, error=str(exc))

    status = "success" if text.strip() else "ocr_required"
    return PDFExtraction(text=text, status=status, pages=len(reader.pages), error=None)
