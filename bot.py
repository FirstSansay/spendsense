"""SpendSense — точка входа Telegram-бота."""

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN


async def main() -> None:
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())