"""Распознавание текста с изображений через tesseract (локальный OCR)."""

import io

import pytesseract
from PIL import Image

# Языки распознавания: русский + английский (цифры, суммы, названия магазинов)
OCR_LANGS = "rus+eng"


def recognize(image_bytes: bytes, lang: str = OCR_LANGS) -> str:
    """Возвращает текст, распознанный с изображения (PNG/JPEG и т.п.).

    При ошибке (нет tesseract, битый файл) возвращает пустую строку —
    вызывающий код перейдёт на запасной путь (vision-модель).
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image, lang=lang)
    except Exception:  # tesseract не установлен, файл не читается и т.п.
        return ""
    return (text or "").strip()


def pdf_to_text(pdf_bytes: bytes) -> str:
    """Извлекает текстовый слой из PDF (первые страницы).

    Возвращает пустую строку, если PDF — это сканы без текстового слоя.
    """
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_bytes))
        parts = [(page.extract_text() or "") for page in reader.pages[:5]]
    except Exception:
        return ""
    return "\n".join(parts).strip()


def pdf_first_page_image(pdf_bytes: bytes, dpi: int = 200) -> bytes | None:
    """Рендерит первую страницу PDF в PNG (их для сканов с чеком).

    Требует poppler-utils (pdftoppm) в системе. None — если не удалось.
    """
    try:
        from pdf2image import convert_from_bytes

        images = convert_from_bytes(pdf_bytes, first_page=1, last_page=1, dpi=dpi)
    except Exception:
        return None
    if not images:
        return None
    buffer = io.BytesIO()
    images[0].save(buffer, format="PNG")
    return buffer.getvalue()