"""Обработчик команды /add — добавление расхода с AI-категоризацией."""

import asyncio

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

import db
from ai_service import ai_service
from handlers.common import parse_amount, parse_date

router = Router(name="expenses")


@router.message(Command("add"))
async def cmd_add(message: Message) -> None:
    text = message.text.removeprefix("/add").strip()
    if not text:
        await message.answer("Укажи расход, например: /add 250 кофе")
        return

    db.get_or_create_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.full_name,
    )

    data = await asyncio.to_thread(ai_service.categorize, text)
    amount = parse_amount(data.get("amount"))
    if data.get("error") or amount is None:
        await message.answer(
            f"🤔 Не смог разобрать: {data.get('error') or 'не указана сумма'}"
        )
        return

    category = data.get("category") or "прочее"
    description = (data.get("description") or "").strip()
    when = parse_date(data.get("date"))

    db.add_transaction(
        user_id=message.from_user.id,
        amount=amount,
        category_name=category,
        description=description,
        when=when,
    )

    # Остаток бюджета за текущий месяц
    start, end = db.current_month_range()
    remaining = db.budget_remaining(message.from_user.id, start, end)

    reply = f"✅ {amount} ₽ — {category}"
    if description:
        reply += f" ({description})"
    if remaining is not None:
        reply += f"\nОстаток бюджета за месяц: {remaining} ₽"
    await message.answer(reply)