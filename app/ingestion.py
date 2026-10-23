from io import BytesIO
from pathlib import Path

import fitz
import pytesseract
from docx import Document as DocxDocument
from PIL import Image


def extract_pages(filename: str, content: bytes, ocr_enabled: bool = True) -> list[dict]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        output = []
        with fitz.open(stream=content, filetype="pdf") as pdf:
            for number, page in enumerate(pdf, start=1):
                text = page.get_text("text").strip()
                used_ocr = False
                if not text and ocr_enabled:
                    try:
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                        text = pytesseract.image_to_string(Image.open(BytesIO(pix.tobytes("png")))).strip()
                        used_ocr = bool(text)
                    except (pytesseract.TesseractNotFoundError, RuntimeError):
                        text = ""
                output.append({"page_number": number, "section": None, "text": text, "ocr": used_ocr})
        return output
    if suffix == ".docx":
        doc = DocxDocument(BytesIO(content))
        text = "\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())
        return [{"page_number": None, "section": None, "text": text, "ocr": False}]
    if suffix == ".txt":
        return [{"page_number": None, "section": None, "text": content.decode("utf-8-sig", errors="replace"), "ocr": False}]
    raise ValueError("Unsupported file type. Allowed: PDF, DOCX, TXT.")


def chunk_pages(pages: list[dict], chunk_size: int = 1200, overlap: int = 160) -> list[dict]:
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")
    output = []
    for page in pages:
        text = page["text"].strip()
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            if end < len(text):
                boundary = text.rfind("\n", start + chunk_size // 2, end)
                if boundary > start:
                    end = boundary
            part = text[start:end].strip()
            if part:
                output.append({"text": part, "page_number": page["page_number"], "section": page.get("section"),
                               "metadata": {"ocr": page.get("ocr", False)}})
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
    return output
