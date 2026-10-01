"""Обёртка над AI API (OpenRouter): категоризация, распознавание речи и чеков.

Промпты для задач лежат в папке prompts/ и подставляются из кода.
Запросы выполняются синхронно (OpenAI SDK); в обработчиках вызываются через
asyncio.to_thread, чтобы не блокировать event loop aiogram.
"""

import base64
import json
import re
from datetime import date
from pathlib import Path

from openai import OpenAI

import config

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# Паттерн «количество/вес × цена» в описании позиции: 2×120, 0.450кг*199.90, 3 х 45
_MULT_RE = re.compile(r"([\d]+[.,]?[\d]*)\s*(?:кг\.?)?\s*[xхX×*]\s*([\d]+[.,]?[\d]*)", re.IGNORECASE)


def _receipt_item_amount(item: dict) -> int | None:
    """Итоговая сумма позиции чека в рублях (целое).

    Если модель вернула цену за единицу вместо итога (типично для «2×120»),
    пересчитываем: количество/вес × цена за единицу.
    """
    try:
        amount = float(str(item.get("amount", "")).replace(",", "."))
    except (TypeError, ValueError, AttributeError):
        return None

    match = _MULT_RE.search(str(item.get("description") or ""))
    if match:
        try:
            first = float(match.group(1).replace(",", "."))
            second = float(match.group(2).replace(",", "."))
        except ValueError:
            first = second = None
        # Если вернулась цена за единицу (second) вместо итога — перемножаем.
        # Проверяем с запасом 1 руб. (модель может округлять цену до целых).
        if first and second and first != 1.0:
            product = first * second
            if abs(amount - second) <= 1.0 and abs(amount - product) > 1.0:
                amount = product
    return int(round(amount))


class AIService:
    """Сервис вызовов AI-моделей через OpenRouter (OpenAI-совместимый API)."""

    def __init__(self) -> None:
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        """Ленивое создание клиента (нужно, чтобы импорт не требовал ключа)."""
        if self._client is None:
            self._client = OpenAI(
                api_key=config.OPENROUTER_API_KEY,
                base_url=config.AI_API_BASE_URL,
            )
        return self._client

    @staticmethod
    def _load_prompt(name: str) -> str:
        return (PROMPTS_DIR / name).read_text(encoding="utf-8")

    def _complete(
        self,
        model: str,
        system: str,
        user_content: list | str,
        *,
        json_mode: bool = False,
    ) -> str:
        """Один вызов chat.completions. Возвращает текст ответа."""
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]
        kwargs: dict = {"model": model, "messages": messages, "temperature": 0}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    def _complete_json(self, model: str, prompt_name: str, user_content: list | str, placeholders: dict | None = None) -> dict:
        """Вызов с JSON-ответом. При ошибке возвращает {"error": описание}."""
        system = self._load_prompt(prompt_name)
        for key, value in (placeholders or {}).items():
            system = system.replace(key, value)
        try:
            payload = json.loads(self._complete(model, system, user_content, json_mode=True))
        except Exception as exc:  # сетевые ошибки, неверный JSON и т.п.
            return {"error": str(exc)}
        if not isinstance(payload, dict):
            return {"error": "неожиданный формат ответа"}
        return payload

    def categorize(self, text: str) -> dict:
        """Категоризирует расход по тексту.

        Возвращает словарь: amount, category, description, date, error.
        Схема ответа задаётся промптом prompts/categorization.txt.
        """
        payload = self._complete_json(
            model=config.AI_MODEL,
            prompt_name="categorization.txt",
            user_content=text,
            placeholders={"{today}": date.today().isoformat()},
        )
        # Нормализация: гарантируем наличие всех ключей
        return {
            "amount": payload.get("amount"),
            "category": payload.get("category"),
            "description": payload.get("description"),
            "date": payload.get("date"),
            "error": payload.get("error"),
        }

    def transcribe(self, audio_bytes: bytes, audio_format: str = "wav") -> str:
        """Распознавание речи (STT) через модель с аудио-входом.

        На вход — байты аудио (WAV и т.п.). Возвращает текст транскрипции.
        При ошибке возвращает пустую строку.
        """
        data_uri = f"data:audio/{audio_format};base64,{base64.b64encode(audio_bytes).decode()}"
        try:
            text = self._complete(
                model=config.AI_MODEL_STT,
                system=self._load_prompt("voice.txt"),
                user_content=[
                    {
                        "type": "input_audio",
                        "input_audio": {"data": data_uri, "format": audio_format},
                    },
                    {"type": "text", "text": "Транскрибируй речь из аудио."},
                ],
            )
        except Exception as exc:  # сетевые ошибки, неподдерживаемый формат и т.п.
            return ""
        return (text or "").strip()

    def parse_receipt(self, ocr_text: str) -> dict:
        """Парсит текст чека (из tesseract OCR) в список покупок.

        Возвращает {"items": [...]} или {"items": [], "error": ...}.
        """
        payload = self._complete_json(
            model=config.AI_MODEL,
            prompt_name="receipt.txt",
            user_content=ocr_text,
        )
        if "error" in payload:
            return {"items": [], "error": payload["error"]}
        items = payload.get("items") or []
        return {"items": self._normalize_receipt_items(items)}

    def parse_receipt_image(self, image_bytes: bytes, mimetype: str = "image/jpeg") -> dict:
        """Парсит чек напрямую по изображению (vision-модель).

        Используется как запасной путь, когда текст OCR слишком плохой.
        """
        data_uri = f"data:{mimetype};base64,{base64.b64encode(image_bytes).decode()}"
        payload = self._complete_json(
            model=config.AI_MODEL_OCR,
            prompt_name="receipt.txt",
            user_content=[
                {"type": "image_url", "image_url": {"url": data_uri}},
                {"type": "text", "text": "Распознай покупки на фото чека."},
            ],
        )
        if "error" in payload:
            return {"items": [], "error": payload["error"]}
        items = payload.get("items") or []
        return {"items": self._normalize_receipt_items(items)}

    @staticmethod
    def _normalize_receipt_items(items: list) -> list:
        """Нормализует позиции чека: сумма — итог строки с учётом количества/веса."""
        if not isinstance(items, list):
            return []
        clean = []
        for item in items:
            if not isinstance(item, dict):
                continue
            copy = dict(item)
            copy["amount"] = _receipt_item_amount(item)
            clean.append(copy)
        return clean


# Единый экземпляр сервиса (переиспользуется во всех обработчиках)
ai_service = AIService()