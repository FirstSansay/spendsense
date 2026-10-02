"""Обработчик команды /report — отчёт и график расходов за месяц.

К отчёту прилагаются кнопки: «PDF-отчёт» (файл с текстом и графиком)
и «💡 Советы» (ИИ-рекомендации по экономии).
"""

import io
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

import db
from handlers.common import bold, esc

router = Router(name="reports")

# DejaVu Sans поддерживает кириллицу — используется по умолчанию в matplotlib
plt.rcParams["font.family"] = "DejaVu Sans"


def _report_data(user_id: int) -> tuple[list[tuple[str, int]], int, int | None]:
    """Сводка, итог и бюджет за текущий месяц."""
    start, end = db.current_month_range()
    rows = db.month_summary(user_id, start, end)
    total = db.month_total(user_id, start, end)
    budget = db.get_budget(user_id)
    return rows, total, budget


def _report_lines(rows: list[tuple[str, int]], total: int, budget: int | None) -> list[str]:
    """Текстовые строки отчёта для PDF (без HTML-разметки)."""
    lines = [f"• {category}: {amount} ₽" for category, amount in rows]
    lines.append("")
    lines.append(f"💰 Итого: {total} ₽")
    if budget:
        lines.append(f"Бюджет: {budget} ₽ (остаток: {budget - total} ₽)")
    return lines


def _report_caption(rows: list[tuple[str, int]], total: int, budget: int | None) -> str:
    """Подпись к графику в чате (Telegram HTML: суммы и категории жирным)."""
    lines = ["📊 Отчёт за текущий месяц:", ""]
    for category, amount in rows:
        lines.append(f"• {esc(category)}: {bold(amount)} ₽")
    lines.append("")
    lines.append(f"💰 Итого: {bold(total)} ₽")
    if budget:
        lines.append(f"Бюджет: {bold(budget)} ₽ (остаток: {bold(budget - total)} ₽)")
    return "\n".join(lines)


def _plot(ax, rows: list[tuple[str, int]]) -> None:
    """Рисует горизонтальную диаграмму расходов по категориям."""
    names = [name for name, _ in rows]
    values = [value for _, value in rows]
    ax.barh(names, values, color="#4a90d9")
    ax.set_title("Расходы по категориям")
    ax.set_xlabel("руб.")
    ax.invert_yaxis()


def _build_chart_png(rows: list[tuple[str, int]]) -> bytes:
    """Диаграмма в PNG (для ответа в чат)."""
    fig, ax = plt.subplots(figsize=(7, 4.5))
    _plot(ax, rows)
    fig.tight_layout()
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=120)
    plt.close(fig)
    buffer.seek(0)
    return buffer.getvalue()


def _build_report_pdf(rows: list[tuple[str, int]], lines: list[str]) -> bytes:
    """PDF-отчёт: страница с текстом + страница с графиком (A4)."""
    # Эмодзи (символы вне BMP) отсутствуют в шрифтах matplotlib — убираем
    safe_lines = [re.sub(r"[^\u0000-\uFFFF]", "", line) for line in lines]
    buffer = io.BytesIO()
    with PdfPages(buffer) as pdf:
        # Страница с текстом
        fig = plt.figure(figsize=(8.27, 11.69))  # A4
        fig.text(0.09, 0.95, "Отчёт SpendSense за месяц", fontsize=16, weight="bold")
        fig.text(0.09, 0.9, "\n".join(safe_lines), fontsize=11, va="top")
        pdf.savefig(fig)
        plt.close(fig)
        # Страница с графиком
        fig, ax = plt.subplots(figsize=(8.27, 5.5))
        _plot(ax, rows)
        pdf.savefig(fig)
        plt.close(fig)
    buffer.seek(0)
    return buffer.getvalue()


def _report_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📄 PDF-отчёт", callback_data="report:pdf")
    builder.button(text="💡 Советы", callback_data="advice:show")
    builder.adjust(2)
    return builder.as_markup()


@router.message(Command("report"))
async def cmd_report(message: Message) -> None:
    db.get_or_create_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.full_name,
    )

    rows, total, budget = _report_data(message.from_user.id)
    if not rows:
        await message.answer("📭 За этот месяц расходов пока нет. Добавь первую: /add 250 кофе")
        return

    caption = _report_caption(rows, total, budget)
    image = _build_chart_png(rows)
    await message.answer_photo(
        BufferedInputFile(image, filename="report.png"),
        caption=caption,
        reply_markup=_report_keyboard(),
    )


@router.callback_query(F.data == "report:pdf")
async def report_pdf(callback: CallbackQuery) -> None:
    rows, total, budget = _report_data(callback.from_user.id)
    if not rows:
        await callback.message.answer("📭 За этот месяц расходов пока нет.")
        await callback.answer()
        return
    await callback.message.answer_document(
        BufferedInputFile(
            _build_report_pdf(rows, _report_lines(rows, total, budget)),
            filename="spendsense-report.pdf",
        ),
        caption="📄 Отчёт за месяц",
    )
    await callback.answer()