"""Обработчик команды /start — регистрация пользователя и приветствие."""

from aiogram import Router
from aiogram.filters import CommandStart
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
        "👋 Привет! Я SpendSense — твой финансовый помощник.\n\n"
        "📝 Записать расход: /add 250 кофе\n"
        "🗣️ Или просто пришли голосовое / фото чека\n"
        "📊 Отчёт за месяц: /report (есть PDF-отчёт)\n"
        "💰 Задать бюджет: /budget 30000\n"
        "💡 Советы по экономии: /advice\n"
        "📄 Выгрузка данных: /export\n\n"
        "Считаем траты вместе! 💸"
    )