"""
Universal resume file parser.
Extracts clean plain text from any uploaded resume: PDF, DOCX, PPTX, or TXT.
"""

from pathlib import Path
from typing import Optional
import pypdf
import docx
from pptx import Presentation


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extracts text from all pages of a PDF file."""
    reader = pypdf.PdfReader(str(pdf_path))
    extracted = []
    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            extracted.append(text.strip())
    return "\n\n".join(extracted)


def extract_text_from_docx(docx_path: Path) -> str:
    """Extracts text from paragraphs and tables of a DOCX file."""
    doc = docx.Document(str(docx_path))
    extracted = []
    for p in doc.paragraphs:
        if p.text.strip():
            extracted.append(p.text.strip())
    for table in doc.tables:
        for row in table.rows:
            row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_text:
                extracted.append(" | ".join(row_text))
    return "\n".join(extracted)


def _extract_shape_text(shape) -> list[str]:
    """Recursively extracts text from a shape or group of shapes."""
    texts = []
    if shape.has_text_frame:
        for p in shape.text_frame.paragraphs:
            if p.text.strip():
                texts.append(p.text.strip())
    elif shape.has_table:
        for row in shape.table.rows:
            row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_text:
                texts.append(" | ".join(row_text))

    if hasattr(shape, "shapes"):
        for sub in shape.shapes:
            texts.extend(_extract_shape_text(sub))
    return texts


def extract_text_from_pptx(pptx_path: Path) -> str:
    """Extracts text from all shapes, groups, and tables in a PPTX presentation."""
    prs = Presentation(str(pptx_path))
    extracted = []
    for slide in prs.slides:
        for shape in slide.shapes:
            extracted.extend(_extract_shape_text(shape))
    return "\n".join(extracted)


def extract_text_from_file(file_path: Path, filename: Optional[str] = None) -> str:
    """
    Extracts text from any supported resume file format based on extension.
    """
    path = Path(file_path)
    name = (filename or path.name).lower()

    if name.endswith(".pdf"):
        return extract_text_from_pdf(path)
    elif name.endswith(".docx") or name.endswith(".doc"):
        return extract_text_from_docx(path)
    elif name.endswith(".pptx") or name.endswith(".ppt"):
        return extract_text_from_pptx(path)
    else:
        # Plain text, markdown, json, etc.
        try:
            return path.read_text(encoding="utf-8").strip()
        except UnicodeDecodeError:
            return path.read_text(encoding="latin-1", errors="ignore").strip()
