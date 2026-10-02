"""SpendSense — точка входа Telegram-бота."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from handlers import advice, budget, expenses, export, export_sheets, receipts, reports, start, voice
import db

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    db.init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрация обработчиков команд
    dp.include_router(start.router)
    dp.include_router(expenses.router)
    dp.include_router(voice.router)
    dp.include_router(receipts.router)
    dp.include_router(reports.router)
    dp.include_router(budget.router)
    dp.include_router(advice.router)
    dp.include_router(export.router)
    dp.include_router(export_sheets.router)

    # Сброс вебхука (на случай, если бот ранее работал как webhook).
    # Не сбрасываем ожидающие обновления: сообщения, присланные пока бот был
    # недоступен, будут доставлены после восстановления соединения.
    try:
        await bot.delete_webhook()
    except Exception:
        logging.warning("Не удалось сбросить вебхук — продолжаем поллинг")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())