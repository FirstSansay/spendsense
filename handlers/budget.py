"""Обработчик команды /budget — установка и просмотр месячного лимита."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

import db
from handlers.common import bold

router = Router(name="budget")


@router.message(Command("budget"))
async def cmd_budget(message: Message) -> None:
    db.get_or_create_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.full_name,
    )

    arg = message.text.removeprefix("/budget").strip()

    # Без аргументов — показать текущий бюджет
    if not arg:
        current = db.get_budget(message.from_user.id)
        if current is None:
            await message.answer("Бюджет не задан. Например: /budget 30000")
            return
        start, end = db.current_month_range()
        remaining = db.budget_remaining(message.from_user.id, start, end)
        await message.answer(
            f"💰 Текущий бюджет: {bold(current)} ₽ (остаток: {bold(remaining)} ₽)"
        )
        return

    if not arg.isdigit() or int(arg) <= 0:
        await message.answer("Укажи лимит положительным числом: /budget 30000")
        return

    amount = int(arg)
    db.set_budget(message.from_user.id, amount)

    start, end = db.current_month_range()
    spent = db.month_total(message.from_user.id, start, end)
    await message.answer(
        f"💰 Бюджет на месяц: {bold(amount)} ₽. Уже потрачено: {bold(spent)} ₽."
    )