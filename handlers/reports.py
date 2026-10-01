"""Обработчик команды /report — отчёт и график расходов за месяц."""

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message

import db

router = Router(name="reports")

# DejaVu Sans поддерживает кириллицу — используется по умолчанию в matplotlib
plt.rcParams["font.family"] = "DejaVu Sans"


def _build_chart(data: list[tuple[str, int]]) -> bytes:
    """Строит горизонтальный график расходов по категориям (PNG)."""
    names = [name for name, _ in data]
    values = [value for _, value in data]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.barh(names, values, color="#4a90d9")
    ax.set_title("Расходы по категориям")
    ax.set_xlabel("руб.")
    ax.invert_yaxis()
    fig.tight_layout()

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=120)
    plt.close(fig)
    buffer.seek(0)
    return buffer.getvalue()


@router.message(Command("report"))
async def cmd_report(message: Message) -> None:
    db.get_or_create_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.full_name,
    )

    start, end = db.current_month_range()
    rows = db.month_summary(message.from_user.id, start, end)
    total = db.month_total(message.from_user.id, start, end)

    if not rows:
        await message.answer("📭 За этот месяц расходов пока нет. Добавь первую: /add 250 кофе")
        return

    lines = ["📊 Отчёт за текущий месяц:", ""]
    for category, amount in rows:
        lines.append(f"• {category}: {amount} ₽")
    lines.append("")
    lines.append(f"💰 Итого: {total} ₽")

    budget = db.get_budget(message.from_user.id)
    if budget:
        remaining = budget - total
        lines.append(f"Бюджет: {budget} ₽ (остаток: {remaining} ₽)")

    image = _build_chart(rows)
    await message.answer_photo(
        BufferedInputFile(image, filename="report.png"),
        caption="\n".join(lines),
    )