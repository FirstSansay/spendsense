"""Обработчик команды /export — выгрузка расходов за месяц в CSV.

CSV в кодировке UTF-8 с разделителем «;» — открывается в Google Sheets,
Excel и любых таблицах без искажения кириллицы.
"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message

import db
from handlers.common import bold

router = Router(name="export")

CSV_HEADER = "дата;категория;описание;сумма\n"


def _to_csv(rows: list[tuple[str, str, str, int]]) -> bytes:
    """Строки (дата, категория, описание, сумма) → CSV-байты (UTF-8 с BOM)."""
    lines = [CSV_HEADER]
    for spent_on, category, description, amount in rows:
        # Экранирование «;» и кавычек не требуется: в данных их нет,
        # но на всякий случай удваиваем кавычки
        desc = description.replace('"', '""')
        lines.append(f"{spent_on};{category};{desc};{amount}\n")
    # BOM нужен, чтобы Excel корректно определил UTF-8
    return ("\ufeff" + "".join(lines)).encode("utf-8")


@router.message(Command("export"))
async def cmd_export(message: Message) -> None:
    db.get_or_create_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.full_name,
    )

    start, end = db.current_month_range()
    rows = db.export_transactions(message.from_user.id, start, end)
    if not rows:
        await message.answer("📭 За этот месяц расходов нет — экспортировать нечего.")
        return

    filename = f"spendsense_{start.strftime('%Y-%m')}.csv"
    total = sum(amount for *_, amount in rows)
    await message.answer_document(
        BufferedInputFile(_to_csv(rows), filename=filename),
        caption=(
            f"📄 Экспорт расходов за {start.strftime('%B %Y')}: "
            f"{bold(len(rows))} записей на {bold(total)} ₽."
        ),
    )