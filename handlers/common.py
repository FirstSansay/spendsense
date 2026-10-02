"""Общие для обработчиков функции и состояния подтверждения (FSM).

Голосовой ввод и чеки проходят подтверждение пользователем перед сохранением —
это требование ТЗ (F7, F8): ИИ может ошибиться, человек решает.
"""

import html as _html
import re
from datetime import date

from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def esc(text: object) -> str:
    """Экранирует текст для Telegram HTML-разметки (& < >)."""
    return _html.escape(str(text), quote=False)


def bold(text: object) -> str:
    return f"<b>{esc(text)}</b>"


def italic(text: object) -> str:
    return f"<i>{esc(text)}</i>"


def code(text: object) -> str:
    return f"<code>{esc(text)}</code>"


def md_to_html(text: str) -> str:
    """Конвертирует минимальное подмножество Markdown в Telegram HTML.

    Используется для ответов ИИ (рекомендации), если модель всё же добавила
    разметку: **жирный**, *курсив*, списки «- »/«* » → HTML + «• ».
    """
    result = _html.escape(str(text), quote=False)
    # **жирный**
    result = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", result, flags=re.S)
    # *курсив* (не трогаем одиночные звёздочки вокруг)
    result = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<i>\1</i>", result)
    # буллеты в начале строк: "- " / "* " → "• "
    result = re.sub(r"^[*-]\s+", "• ", result, flags=re.M)
    return result


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