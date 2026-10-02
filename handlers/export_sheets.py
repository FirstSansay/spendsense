"""Обработчик команды /export_sheets — выгрузка расходов в Google Sheets.

Требует настройки (переменные окружения / .env):
  GOOGLE_CREDENTIALS_JSON или GOOGLE_CREDENTIALS_PATH — ключ Service Account;
  GOOGLE_SHEET_ID — ID таблицы (из URL); GOOGLE_SHEET_RANGE — имя листа.
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

    start, end = db.current_month_range()
    rows = db.export_transactions(message.from_user.id, start, end)
    if not rows:
        await message.answer("📭 За этот месяц расходов нет — экспортировать нечего.")
        return

    wait_msg = await message.answer("☁️ Выгружаю в Google Sheets…")
    ok, detail = await asyncio.to_thread(
        sheets_service.export_month, config.GOOGLE_SHEET_ID, rows
    )

    if ok:
        link = f"https://docs.google.com/spreadsheets/d/{config.GOOGLE_SHEET_ID}/edit"
        await wait_msg.edit_text(
            f"✅ Расходы за {start.strftime('%B %Y')} выгружены в таблицу "
            f"({bold(len(rows))} записей, {esc(detail)}).\n"
            f"Открыть: <a href=\"{link}\">таблицу</a>"
        )
    else:
        await wait_msg.edit_text(f"🤔 Не удалось выгрузить: {esc(detail)}")