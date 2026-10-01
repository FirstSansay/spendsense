"""Обработчик команды /add — добавление расхода с AI-категоризацией."""

from datetime import date

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

import db
from ai_service import ai_service

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

    data = ai_service.categorize(text)
    if data.get("error") or not data.get("amount"):
        await message.answer(
            f"🤔 Не смог разобрать: {data.get('error') or 'не указана сумма'}"
        )
        return

    try:
        amount = int(round(float(data["amount"])))
    except (TypeError, ValueError):
        await message.answer("🤔 Не удалось определить сумму. Попробуй ещё раз: /add 250 кофе")
        return

    category = data.get("category") or "прочее"
    description = (data.get("description") or "").strip()

    # Дата из модели, при невалидном значении — сегодня
    when = date.today()
    try:
        when = date.fromisoformat(data["date"])
    except (TypeError, ValueError):
        pass

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