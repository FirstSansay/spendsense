"""Обработчик команды /export_sheets — выгрузка расходов в Google Sheets.

Каждому пользователю создаётся ОТДЕЛЬНЫЙ лист (имя — username или user_<id>),
в него записывается вся история расходов пользователя (перезапись, без дублей).

Требует настройки (переменные окружения / .env):
  GOOGLE_CREDENTIALS_JSON или GOOGLE_CREDENTIALS_PATH — ключ Service Account;
  GOOGLE_SHEET_ID — ID таблицы (из URL).
Таблицу нужно открыть для доступа email сервисного аккаунта (редактор).
"""

import asyncio

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

import config
import db
import sheets_service
from handlers.common import bold, esc

router = Router(name="export_sheets")


@router.message(Command("export_sheets"))
async def cmd_export_sheets(message: Message) -> None:
    db.get_or_create_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.full_name,
    )

    if not config.GOOGLE_SHEET_ID:
        await message.answer(
            "⚙️ Google Sheets не настроен.\n"
            "Нужно задать GOOGLE_SHEET_ID и ключ Service Account "
            "(см. README → «Экспорт в Google Sheets»)."
        )
        return

    # Личный лист пользователя + вся его история расходов
    title = sheets_service.sheet_title(
        message.from_user.username, message.from_user.first_name, message.from_user.id
    )
    rows = db.export_all_transactions(message.from_user.id)
    if not rows:
        await message.answer("📭 Расходов пока нет - экспортировать нечего.")
        return

    wait_msg = await message.answer("☁️ Выгружаю в свой лист Google Sheets…")
    ok, detail = await asyncio.to_thread(
        sheets_service.export_user_sheet, config.GOOGLE_SHEET_ID, title, rows
    )

    if ok:
        link = f"https://docs.google.com/spreadsheets/d/{config.GOOGLE_SHEET_ID}/edit"
        await wait_msg.edit_text(
            f"✅ Расходы записаны в твой лист <b>{esc(title)}</b> "
            f"({bold(len(rows))} записей, {esc(detail)}).\n"
            f"Открыть: <a href=\"{link}\">таблицу</a>"
        )
    else:
        await wait_msg.edit_text(f"🤔 Не удалось выгрузить: {esc(detail)}")