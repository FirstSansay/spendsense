# SpendSense — AI-ассистент для управления личными финансами

Telegram-бот для учёта личных расходов: приём через текст, голос и фото чеков,
автоматическая категоризация трат через ИИ, отчёты по периодам и рекомендации по экономии.

## Возможности

- Добавление расходов текстом (`/add 250 кофе`)
- Голосовой ввод расходов
- Распознавание фото чеков (OCR)
- AI-категоризация покупок
- Отчёты за неделю/месяц с графиками
- Настройка бюджета и контроль трат

## Технологии

Python · aiogram 3 · SQLAlchemy (SQLite/PostgreSQL) · AI API (OpenAI/GigaChat) · OCR · TTS/STT

## Запуск

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # подставь свои токены
python bot.py
```

Не забудь создать бота у [@BotFather](https://t.me/BotFather) и получить токен.

## Структура

```
SpendSense/
├── bot.py          # точка входа
├── db.py           # работа с базой данных
├── ai_service.py   # обёртка над AI API
├── handlers/       # обработчики команд
├── prompts/        # библиотека промптов
└── requirements.txt
```

## Библиотека промптов

Все использованные промпты собраны в [docs/prompts.md](docs/prompts.md).

---

Автор: <твоё имя>
Лицензия: MIT