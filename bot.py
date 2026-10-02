"""SpendSense — точка входа Telegram-бота."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, MenuButtonCommands

from config import BOT_TOKEN
from handlers import advice, budget, expenses, export, export_sheets, receipts, reports, reset, start, voice
import db

logging.basicConfig(level=logging.INFO)

# Команды кнопки «Меню» Telegram — соответствуют функционалу проекта
MENU_COMMANDS = [
    BotCommand(command="start", description="Приветствие и начало работы"),
    BotCommand(command="help", description="Справка по командам"),
    BotCommand(command="add", description="Записать расход: /add 250 кофе"),
    BotCommand(command="report", description="Отчёт за месяц с графиком"),
    BotCommand(command="budget", description="Задать бюджет: /budget 30000"),
    BotCommand(command="advice", description="Советы по экономии"),
    BotCommand(command="export", description="Выгрузка данных в CSV"),
    BotCommand(command="export_sheets", description="Экспорт в Google Sheets"),
    BotCommand(command="reset", description="Сбросить свои данные"),
]


async def _setup_bot_menu(bot: Bot) -> None:
    """Устанавливает команды кнопки «Меню» и гарантирует её наличие.

    Тип кнопки «commands» показывает список команд под полем ввода.
    """
    await bot.set_my_commands(MENU_COMMANDS)
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())


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
    dp.include_router(reset.router)

    # Сброс вебхука (на случай, если бот ранее работал как webhook).
    # Не сбрасываем ожидающие обновления: сообщения, присланные пока бот был
    # недоступен, будут доставлены после восстановления соединения.
    try:
        await bot.delete_webhook()
    except Exception:
        logging.warning("Не удалось сбросить вебхук — продолжаем поллинг")

    # Кнопка «Меню» с командами проекта
    try:
        await _setup_bot_menu(bot)
    except Exception:
        logging.warning("Не удалось установить меню команд")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())