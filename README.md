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

## Виртуальное окружение (.venv)

Проект использует виртуальное окружение `.venv` — оно уже создано в папке проекта и не попадает в git (см. `.gitignore`). Используй его при каждом запуске и установке зависимостей.

**Активация:**

```bash
# Linux / macOS
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (CMD)
.venv\Scripts\activate.bat
```

После активации в начале строки терминала появляется `(.venv)` — окружение активно.

**Проверка версии Python в окружении:**

```bash
.venv/bin/python --version   # Linux / macOS
```

**Установка зависимостей** (при первичной настройке или после изменения `requirements.txt`):

```bash
pip install -r requirements.txt
```

**Деактивация окружения:**

```bash
deactivate
```

**Пересоздание окружения (если что-то сломалось):**

```bash
rm -rf .venv
python3 -m venv .venv
```

## Запуск

```bash
source .venv/bin/activate          # активировать окружение
pip install -r requirements.txt    # установить зависимости
cp .env.example .env               # подставить свои токены
python bot.py                      # запустить бота
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