"""Обработчик чеков: фото, документы-изображения и PDF.

Основной путь: tesseract извлекает текст → промпт receipt.txt (V4 Flash)
парсит список покупок. Если текст OCR слишком плохой — запасной путь:
прямое распознавание изображения vision-моделью (deepseek-v4.1-flash).
PDF-чеки: сначала текстовый слой, при его отсутствии — рендер первой
страницы и стандартный путь по изображению.
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


async def _show_items_confirmation(message: Message, state: FSMContext, items: list[dict]) -> None:
    """Показывает список покупок и кнопку сохранения (общее для фото и PDF)."""
    total = sum(item["amount"] for item in items)
    await state.set_state(ConfirmState.receipt)
    await state.update_data(items=items)

    lines = [f"В чеке {len(items)} позиций на {total} ₽:", ""]
    for item in items:
        desc = item["description"] or "—"
        lines.append(f"• {desc} — {item['amount']} ₽ ({item['category']})")
    await message.edit_text(
        "\n".join(lines) + "\n\nСохранить покупки?",
        reply_markup=confirm_keyboard("receipt"),
    )


async def _handle_receipt(target: Message, bot: Bot, state: FSMContext, image_bytes: bytes, mimetype: str) -> None:
    # target — сообщение бота («🧾 Распознаю чек…»), его и редактируем
    db.get_or_create_user(
        tg_id=target.from_user.id,
        username=target.from_user.username,
        first_name=target.from_user.full_name,
    )

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
        await target.edit_text(f"🤔 Не удалось распознать чек{hint}. Попробуй фото почетче и без бликов.")
        return

    await _show_items_confirmation(target, state, items)


@router.message(F.photo)
async def cmd_photo(message: Message, bot: Bot, state: FSMContext) -> None:
    """Фото чека (самое большое в наборе)."""
    wait_msg = await message.answer("🧾 Распознаю чек…")
    file_id = message.photo[-1].file_id
    image_bytes = (await bot.download(file_id)).getvalue()
    await _handle_receipt(wait_msg, bot, state, image_bytes, mimetype="image/jpeg")


@router.message(F.document, F.document.mime_type.startswith("image/"))
async def cmd_document_image(message: Message, bot: Bot, state: FSMContext) -> None:
    """Документ-изображение (сканы, сохранённые фото)."""
    wait_msg = await message.answer("🧾 Распознаю чек…")
    image_bytes = (await bot.download(message.document.file_id)).getvalue()
    mimetype = message.document.mime_type or "image/jpeg"
    await _handle_receipt(wait_msg, bot, state, image_bytes, mimetype=mimetype)


@router.message(F.document, F.document.mime_type == "application/pdf")
async def cmd_document_pdf(message: Message, bot: Bot, state: FSMContext) -> None:
    """PDF-чек: сначала текстовый слой, при его отсутствии — рендер страницы."""
    db.get_or_create_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.full_name,
    )
    wait_msg = await message.answer("🧾 Читаю PDF-чек…")
    pdf_bytes = (await bot.download(message.document.file_id)).getvalue()

    text_layer = await asyncio.to_thread(ocr_service.pdf_to_text, pdf_bytes)
    if _looks_like_receipt(text_layer):
        parsed = await asyncio.to_thread(ai_service.parse_receipt, text_layer)
        items = _clean_items(parsed.get("items") or [])
        if items:
            await _show_items_confirmation(wait_msg, state, items)
            return

    # Нет текстового слоя (скан): рендерим первую страницу и идём обычным путём
    image = await asyncio.to_thread(ocr_service.pdf_first_page_image, pdf_bytes)
    if image is None:
        await wait_msg.edit_text("🤔 Не удалось открыть PDF-чек.")
        return
    await _handle_receipt(message=wait_msg, bot=bot, state=state, image_bytes=image, mimetype="image/png")


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