"""Обёртка над AI API (OpenRouter): категоризация расходов и парсинг данных.

Промпты для задач лежат в папке prompts/ и подставляются из кода.
"""

import json
from datetime import date
from pathlib import Path

from openai import OpenAI

import config

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


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

    def categorize(self, text: str) -> dict:
        """Категоризирует расход по тексту.

        Возвращает словарь: amount, category, description, date, error.
        Схема ответа задаётся промптом prompts/categorization.txt.
        """
        system = self._load_prompt("categorization.txt").replace(
            "{today}", date.today().isoformat()
        )
        try:
            response = self.client.chat.completions.create(
                model=config.AI_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": text},
                ],
                response_format={"type": "json_object"},
                temperature=0,
            )
            payload = json.loads(response.choices[0].message.content)
        except Exception as exc:  # сетевые ошибки, неверный JSON и т.п.
            return {
                "amount": None,
                "category": None,
                "description": None,
                "date": None,
                "error": f"Ошибка AI: {exc}",
            }
        # Нормализация: гарантируем наличие всех ключей
        return {
            "amount": payload.get("amount"),
            "category": payload.get("category"),
            "description": payload.get("description"),
            "date": payload.get("date"),
            "error": payload.get("error"),
        }


# Единый экземпляр сервиса (переиспользуется во всех обработчиках)
ai_service = AIService()