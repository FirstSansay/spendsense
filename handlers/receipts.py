"""Обработчик фото чеков: OCR (tesseract) → парсинг → подтверждение.

Основной путь: tesseract извлекает текст с фото → промпт receipt.txt (V4 Flash)
парсит список покупок. Если текст OCR слишком плохой — запасной путь: прямое
распознавание изображения vision-моделью (deepseek-v4.1-flash).
"""

import asyncio
import re
from datetime import date

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import db
import ocr_service
from ai_service import ai_service
from handlers.common import ConfirmState, confirm_keyboard, parse_amount

router = Router(name="receipts")


def _looks_like_receipt(text: str) -> bool:
    """Текст похож на чек: есть буквы и хотя бы одна цифра."""
    return (
        len(text) >= 10
        and bool(re.search(r"\d", text))
        and bool(re.search(r"[А-Яа-яA-Za-z]", text))
    )


def _clean_items(items: list) -> list[dict]:
    """Фильтрует позиции чека: только с корректной суммой.

    Если ИИ вернул количество/вес (quantity), добавляет его в описание
    («2× молоко»), чтобы в отчёте было видно итог за несколько единиц.
    """
    clean = []
    for item in items:
        if not isinstance(item, dict):
            continue
        amount = parse_amount(item.get("amount"))
        if amount is None or amount <= 0:
            continue

        description = (item.get("description") or "").strip()
        try:
            quantity = float(str(item.get("quantity") or "").replace(",", "."))
        except (TypeError, ValueError):
            quantity = None
        # Признак «2×120» уже есть в описании — не дублируем
        if quantity is not None and quantity != 1.0 and not re.search(r"[xхX×*]", description):
            description = f"{quantity:g}× {description}".strip()

        clean.append({
            "amount": amount,
            "category": (item.get("category") or "прочее").strip(),
            "description": description,
        })
    return clean


async def _handle_receipt(message: Message, bot: Bot, state: FSMContext, image_bytes: bytes, mimetype: str) -> None:
    db.get_or_create_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.full_name,
    )

    wait_msg = await message.answer("🧾 Распознаю чек…")

    # Основной путь: локальный OCR (tesseract) → текст → AI-парсинг
    ocr_text = await asyncio.to_thread(ocr_service.recognize, image_bytes)
    if _looks_like_receipt(ocr_text):
        parsed = await asyncio.to_thread(ai_service.parse_receipt, ocr_text)
    else:
        # Запасной путь: vision-модель по изображению напрямую
        parsed = await asyncio.to_thread(ai_service.parse_receipt_image, image_bytes, mimetype)

    items = _clean_items(parsed.get("items") or [])
    if not items:
        hint = "" if _looks_like_receipt(ocr_text) else " (текст OCR слишком плохой — подключён vision)"
        await wait_msg.edit_text(f"🤔 Не удалось распознать чек{hint}. Попробуй фото почетче и без бликов.")
        return

    total = sum(item["amount"] for item in items)
    await state.set_state(ConfirmState.receipt)
    await state.update_data(items=items)

    lines = [f"В чеке {len(items)} позиций на {total} ₽:", ""]
    for item in items:
        desc = item["description"] or "—"
        lines.append(f"• {desc} — {item['amount']} ₽ ({item['category']})")
    await wait_msg.edit_text(
        "\n".join(lines) + "\n\nСохранить покупки?",
        reply_markup=confirm_keyboard("receipt"),
    )


@router.message(F.photo)
async def cmd_photo(message: Message, bot: Bot, state: FSMContext) -> None:
    """Фото чека (самое большое в наборе)."""
    file_id = message.photo[-1].file_id
    image_bytes = (await bot.download(file_id)).getvalue()
    await _handle_receipt(message, bot, state, image_bytes, mimetype="image/jpeg")


@router.message(F.document, F.document.mime_type.startswith("image/"))
async def cmd_document_image(message: Message, bot: Bot, state: FSMContext) -> None:
    """Документ-изображение (сканы, сохранённые фото)."""
    image_bytes = (await bot.download(message.document.file_id)).getvalue()
    mimetype = message.document.mime_type or "image/jpeg"
    await _handle_receipt(message, bot, state, image_bytes, mimetype=mimetype)


@router.callback_query(ConfirmState.receipt, F.data == "receipt:save")
async def save_receipt(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    items = data.get("items") or []
    today = date.today()
    for item in items:
        db.add_transaction(
            user_id=callback.from_user.id,
            amount=item["amount"],
            category_name=item["category"],
            description=item["description"],
            when=today,
        )
    await state.clear()
    total = sum(item["amount"] for item in items)
    await callback.message.edit_text(f"✅ Сохранено позиций: {len(items)} на {total} ₽.")
    await callback.answer()


@router.callback_query(ConfirmState.receipt, F.data == "receipt:cancel")
async def cancel_receipt(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Отменено.")
    await callback.answer()