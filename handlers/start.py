"""Обработчики /start и /help — приветствие и подсказка по командам."""

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

import db

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    db.get_or_create_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.full_name,
    )
    await message.answer(
        "👋 Привет! Я SpendSense - твой финансовый помощник.\n\n"
        "📝 Записать расход: /add 250 кофе\n"
        "🗣️ Или просто пришли голосовое / фото чека\n"
        "📊 Отчёт за месяц: /report (есть PDF-отчёт)\n"
        "💰 Задать бюджет: /budget 30000\n"
        "💡 Советы по экономии: /advice\n"
        "📄 Выгрузка данных: /export\n\n"
        "Справка по командам: /help\n"
        "Считаем траты вместе! 💸"
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "🤖 Помощь по SpendSense\n\n"
        "📝 Расходы текстом:\n"
        "/add 250 кофе - записать трату\n"
        "После /add можно исправить категорию кнопкой - бот запомнит\n\n"
        "🎤 Голосом:\n"
        "пришли голосовое - например, «двести пятьдесят на кофе»\n\n"
        "🧾 Чеки:\n"
        "пришли фото, документ или PDF чека - бот распознает покупки\n\n"
        "📊 Отчёты и бюджет:\n"
        "/report - отчёт за месяц с графиком (+ кнопка PDF-отчёта)\n"
        "/budget 30000 - задать месячный лимит\n"
        "/advice - ИИ-рекомендации по экономии\n\n"
        "📤 Экспорт:\n"
        "/export - выгрузить данные в CSV\n"
        "/export_sheets - записать расходы в Google Sheets\n\n"
        "Просто попробуй - всё считается само! 💸"
    )