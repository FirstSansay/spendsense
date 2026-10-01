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