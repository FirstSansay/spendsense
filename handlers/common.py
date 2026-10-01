"""Общие для обработчиков функции и состояния подтверждения (FSM).

Голосовой ввод и чеки проходят подтверждение пользователем перед сохранением —
это требование ТЗ (F7, F8): ИИ может ошибиться, человек решает.
"""

from datetime import date

from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


class ConfirmState(StatesGroup):
    """Состояния ожидания подтверждения («сохранить/отменить»)."""

    voice = State()     # голосовое сообщение
    receipt = State()   # фото чека


def parse_amount(value: object) -> int | None:
    """Безопасно превращает сумму из ответа ИИ в целое число рублей."""
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def parse_date(value: object) -> date:
    """Дата из ответа ИИ; при невалидном значении — сегодня."""
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return date.today()


def confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    """Кнопки подтверждения: сохранить / отменить."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Сохранить", callback_data=f"{action}:save")
    builder.button(text="❌ Отменить", callback_data=f"{action}:cancel")
    builder.adjust(2)
    return builder.as_markup()