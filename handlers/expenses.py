"""Обработчик команды /add — добавление расхода с AI-категоризацией.

После сохранения можно исправить категорию («обучение на правках»):
выбранная категория запоминается в БД и применяется без вызова ИИ для
похожих описаний в будущем.
"""

import asyncio

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

import db
from ai_service import ai_service
from handlers.common import bold, code, esc, parse_amount, parse_date

router = Router(name="expenses")


def _fix_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Сменить категорию", callback_data="fixcat:open")
    return builder.as_markup()


def _categories_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for name in db.DEFAULT_CATEGORIES:
        builder.button(text=name, callback_data=f"fixcat:set:{name}")
    builder.adjust(2)
    return builder.as_markup()


@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext) -> None:
    text = message.text.removeprefix("/add").strip()
    if not text:
        await message.answer(
            f"Укажи расход, например: {code('/add 250 кофе')}"
        )
        return

    db.get_or_create_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.full_name,
    )

    data = await asyncio.to_thread(ai_service.categorize, text, message.from_user.id)
    amount = parse_amount(data.get("amount"))
    if data.get("error") or amount is None:
        await message.answer(
            f"🤔 Не смог разобрать: {esc(data.get('error') or 'не указана сумма')}"
        )
        return

    category = data.get("category") or "прочее"
    description = (data.get("description") or "").strip()
    when = parse_date(data.get("date"))

    transaction = db.add_transaction(
        user_id=message.from_user.id,
        amount=amount,
        category_name=category,
        description=description,
        when=when,
    )
    # Для кнопки «сменить категорию» запоминаем id сохранённого расхода
    await state.update_data(last_tx_id=transaction.id)

    # Остаток бюджета за текущий месяц
    start, end = db.current_month_range()
    remaining = db.budget_remaining(message.from_user.id, start, end)

    reply = f"✅ {bold(amount)} ₽ - {bold(category)}"
    if data.get("by_rule"):
        reply += " (по запомненному правилу)"
    if description:
        reply += f" ({esc(description)})"
    if remaining is not None:
        reply += f"\nОстаток бюджета за месяц: {bold(remaining)} ₽"
    await message.answer(reply, reply_markup=_fix_keyboard())


@router.callback_query(F.data == "fixcat:open")
async def fix_category_open(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "✏️ Выбери правильную категорию для последнего расхода:",
        reply_markup=_categories_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("fixcat:set:"))
async def fix_category_set(callback: CallbackQuery, state: FSMContext) -> None:
    category = callback.data.split(":", 2)[2]
    data = await state.get_data()
    tx_id = data.get("last_tx_id")

    if tx_id is None:
        await callback.message.edit_text(
            "Не знаю, какой расход исправить - добавь ещё раз через /add."
        )
        await callback.answer()
        return

    # Правка категории в БД + запоминание правила «описание → категория»
    tx = db.get_transaction(tx_id)
    db.update_transaction_category(tx_id, category)
    description = tx.description if tx else ""
    db.remember_category_rule(callback.from_user.id, description, category)

    await callback.message.edit_text(
        f"✅ Категория изменена на {bold(category)} и запомнена."
    )
    await callback.answer()


@router.callback_query(F.data == "fixcat:cancel")
async def fix_category_cancel(callback: CallbackQuery) -> None:
    await callback.message.edit_text("❌ Отменено.")
    await callback.answer()