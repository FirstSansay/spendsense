"""Конфигурация проекта. Читает настройки из переменных окружения / .env."""

import os

from dotenv import load_dotenv

load_dotenv()

# Токен Telegram-бота
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# --- OpenRouter (единый шлюз к AI-моделям, OpenAI-совместимый API) ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
AI_API_BASE_URL = os.getenv("AI_API_BASE_URL", "https://openrouter.ai/api/v1")

# Основная модель DeepSeek для текстовых задач (категоризация, парсинг, рекомендации)
AI_MODEL = os.getenv("AI_MODEL", "deepseek/deepseek-v4-flash")

# Модель для распознавания чеков: запасной путь (vision), если tesseract OCR не справился.
# Основной путь — tesseract OCR + AI-парсинг текста через AI_MODEL.
AI_MODEL_OCR = os.getenv("AI_MODEL_OCR", "deepseek/deepseek-v4.1-flash")

# Модель для распознавания речи (аудио-вход)
AI_MODEL_STT = os.getenv("AI_MODEL_STT", "qwen/qwen3.8-omni-flash")

# База данных (SQLite для MVP, далее PostgreSQL)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///spendsense.db")