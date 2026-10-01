"""Обработчик команды /advice — ИИ-рекомендации по экономии.

Строит текстовую сводку расходов за месяц и передаёт её модели
(промпт recommendations.txt); доступно также кнопкой из отчёта.
"""

import asyncio
from datetime import date

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

import db
from ai_service import ai_service

router = Router(name="advice")


def _summary_text(user_id: int) -> str:
    """Сводка расходов за текущий месяц для ИИ-рекомендаций."""
    start, end = db.current_month_range()
    rows = db.month_summary(user_id, start, end)
    total = db.month_total(user_id, start, end)
    budget = db.get_budget(user_id)

    lines = [f"Расходы за {start.strftime('%B %Y')}:", ""]
    for category, amount in rows:
        lines.append(f"- {category}: {amount} ₽")
    lines.append(f"ИТОГО: {total} ₽")
    if budget:
        lines.append(f"Бюджет месяца: {budget} ₽, остаток: {budget - total} ₽")
    else:
        lines.append("Бюджет не задан.")
    return "\n".join(lines)


async def _send_advice(user_id: int, target: Message | CallbackQuery) -> None:
    text = _summary_text(user_id)
    if "ИТОГО: 0 ₽" in text:
        await target.answer("📭 За этот месяц расходов ещё нет — сначала добавь несколько трат.")
        return
    reply = await asyncio.to_thread(ai_service.recommendations, text)
    await target.answer(f"💡 Рекомендации по экономии:\n\n{reply}")


@router.message(Command("advice"))
async def cmd_advice(message: Message) -> None:
    db.get_or_create_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.full_name,
    )
    await _send_advice(message.from_user.id, message)


@router.callback_query(F.data == "advice:show")
async def advice_show(callback: CallbackQuery) -> None:
    await _send_advice(callback.from_user.id, callback.message)
    await callback.answer()