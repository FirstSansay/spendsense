"""Обработчик команды /reset - полный сброс данных пользователя.

Перед удалением показывается подробный список того, что будет удалено,
и нажимается явное подтверждение. Действие необратимо.
"""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

import db
from handlers.common import bold

router = Router(name="reset")


def _confirm_keyboard() -> InlineKeyboardMarkup:
    """Кнопки подтверждения сброса."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить сброс", callback_data="reset:confirm")
    builder.button(text="❌ Отмена", callback_data="reset:cancel")
    builder.adjust(2)
    return builder.as_markup()


def _format_summary(info: dict) -> str:
    """Подробный список того, что будет удалено."""
    lines = []
    if info["transactions"]:
        lines.append(f"🗃 <b>Транзакции</b> - {info['transactions']} шт. на сумму {bold(info['amount'])} ₽")
    if info["budget"] is not None:
        lines.append(f"💰 <b>Бюджет месяца</b> - {bold(info['budget'])} ₽")
    if info["rules"]:
        lines.append(f"🎓 <b>Запомненные правила</b> (обучение категориям) - {bold(info['rules'])} шт.")
    if not lines:
        lines.append("Нет данных этого пользователя.")
    return "\n".join(lines)


@router.message(Command("reset"))
async def cmd_reset(message: Message) -> None:
    info = db.user_reset_summary(message.from_user.id)
    if not info["user_exists"] and info["transactions"] == 0 and info["rules"] == 0 and info["budget"] is None:
        await message.answer("📭 У тебя пока нет данных - сбрасывать нечего.")
        return

    await message.answer(
        "⚠️ <b>Полный сброс данных</b>\n\n"
        "Будут удалены:\n"
        f"{_format_summary(info)}\n\n"
        "Это действие <b>необратимо</b>. Твой профиль, траты и правила будут "
        "очищены навсегда. Категории по умолчанию останутся.\n\n"
        "Продолжить?",
        reply_markup=_confirm_keyboard(),
    )


@router.callback_query(F.data == "reset:confirm")
async def reset_confirm(callback: CallbackQuery) -> None:
    removed = db.reset_user(callback.from_user.id)

    parts = []
    if removed["transactions"]:
        parts.append(f"транзакции: {removed['transactions']} шт. на {bold(removed['amount'])} ₽")
    if removed["budget"] is not None:
        parts.append(f"бюджет: {bold(removed['budget'])} ₽")
    if removed["rules"]:
        parts.append(f"правила: {bold(removed['rules'])} шт.")

    text = "✅ Данные сброшены: " + (", ".join(parts) if parts else "данных не было") + "."
    await callback.message.edit_text(text)
    await callback.answer()


@router.callback_query(F.data == "reset:cancel")
async def reset_cancel(callback: CallbackQuery) -> None:
    await callback.message.edit_text("❌ Отмена - данные не тронуты.")
    await callback.answer()