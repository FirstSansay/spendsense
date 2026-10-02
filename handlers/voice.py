"""Обработчик голосовых сообщений: STT → категоризация → подтверждение.

Поток: голосовое (OGG) → ffmpeg в WAV 16 кГц → транскрибация моделью с
аудио-входом (qwen omni) → категоризация текста → подтверждение пользователем.
"""

import asyncio
import subprocess

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram import Bot

import db
from ai_service import ai_service
from handlers.common import (
    ConfirmState,
    bold,
    confirm_keyboard,
    esc,
    parse_amount,
    parse_date,
)

router = Router(name="voice")


def _ogg_to_wav(data: bytes) -> bytes:
    """Конвертирует OGG/Opus (голосовое из Telegram) в WAV 16 кГц моно."""
    proc = subprocess.run(
        [
            "ffmpeg", "-i", "pipe:0",
            "-f", "wav", "-ar", "16000", "-ac", "1",
            "-y", "pipe:1",
        ],
        input=data,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=True,
        timeout=60,
    )
    return proc.stdout


@router.message(F.voice)
async def cmd_voice(message: Message, bot: Bot, state: FSMContext) -> None:
    db.get_or_create_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.full_name,
    )

    wait_msg = await message.answer("🎤 Распознаю речь…")
    try:
        ogg_data = (await bot.download(message.voice.file_id)).getvalue()
        wav_data = await asyncio.to_thread(_ogg_to_wav, ogg_data)
        text = await asyncio.to_thread(ai_service.transcribe, wav_data, "wav")
    except Exception as exc:
        await wait_msg.edit_text(f"🤔 Не удалось разобрать голосовое: {esc(exc)}")
        return

    if not text:
        await wait_msg.edit_text("🤔 Не расслышал речь. Попробуй ещё раз.")
        return

    parsed = await asyncio.to_thread(ai_service.categorize, text, message.from_user.id)
    amount = parse_amount(parsed.get("amount"))
    if parsed.get("error") or amount is None:
        await wait_msg.edit_text(
            f"🤔 В сообщении не нашёл сумму: {esc(parsed.get('error') or '')}"
        )
        return

    category = parsed.get("category") or "прочее"
    description = (parsed.get("description") or "").strip()

    await state.set_state(ConfirmState.voice)
    await state.update_data(
        amount=amount,
        category=category,
        description=description,
        when=parse_date(parsed.get("date")),
    )

    reply = f"🎤 Распознал: {bold(amount)} ₽ - {bold(category)}"
    if description:
        reply += f" ({esc(description)})"
    await wait_msg.edit_text(
        reply + "\n\nСохранить расход?",
        reply_markup=confirm_keyboard("voice"),
    )


@router.callback_query(ConfirmState.voice, F.data == "voice:save")
async def save_voice(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    db.add_transaction(
        user_id=callback.from_user.id,
        amount=data["amount"],
        category_name=data["category"],
        description=data.get("description", ""),
        when=data["when"],
    )
    await state.clear()
    await callback.message.edit_text("✅ Расход сохранён.")
    await callback.answer()


@router.callback_query(ConfirmState.voice, F.data == "voice:cancel")
async def cancel_voice(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Отменено.")
    await callback.answer()