"""Работа с базой данных: пользователи, категории, транзакции, бюджет.

Для MVP используется SQLite, далее возможен переход на PostgreSQL (config.DATABASE_URL).
"""

from datetime import date, datetime, timezone

from sqlalchemy import ForeignKey, create_engine, delete, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from config import DATABASE_URL

# SQLite: один поток на обработчик; флаг для корректной работы с aiogram
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

# Стандартный список категорий
DEFAULT_CATEGORIES = [
    "продукты",
    "транспорт",
    "кафе и рестораны",
    "развлечения",
    "здоровье",
    "дом",
    "связь",
    "одежда",
    "образование",
    "прочее",
]


class Base(DeclarativeBase):
    """Базовый класс всех моделей БД."""


class User(Base):
    """Пользователь (идентификатор — Telegram ID)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str | None]
    first_name: Mapped[str | None]
    monthly_budget: Mapped[int | None] = mapped_column(default=None)  # лимит на месяц, руб.
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user")


class Category(Base):
    """Категория расходов."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="category")


class Transaction(Base):
    """Одна запись о расходе."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    amount: Mapped[int]  # сумма в рублях (целое число)
    description: Mapped[str] = mapped_column(default="")
    spent_on: Mapped[date] = mapped_column("date", default=date.today)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    user: Mapped[User] = relationship(back_populates="transactions")
    category: Mapped[Category] = relationship(back_populates="transactions")


class CategoryRule(Base):
    """Правило «запомненной» категории: значимые слова из описания → категория.

    Служит для «обучения на правках»: если пользователь исправил категорию
    расхода, правило запоминается и применяется в следующий раз без вызова ИИ,
    когда в новом тексте встречаются те же значимые слова.
    """

    __tablename__ = "category_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    keyword: Mapped[str]  # значимые слова описания (нижний регистр, через пробел)
    category: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


def init_db() -> None:
    """Создаёт таблицы и заполняет категории по умолчанию."""
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        existing = {name for (name,) in session.execute(select(Category.name))}
        for name in DEFAULT_CATEGORIES:
            if name not in existing:
                session.add(Category(name=name))
        session.commit()


def get_or_create_user(tg_id: int, username: str | None = None, first_name: str | None = None) -> User:
    """Возвращает пользователя, создавая его при первом обращении."""
    with SessionLocal() as session:
        user = session.get(User, tg_id)
        if user is None:
            user = User(id=tg_id, username=username, first_name=first_name)
            session.add(user)
            session.commit()
        return user


def add_transaction(
    user_id: int,
    amount: int,
    category_name: str,
    description: str = "",
    when: date | None = None,
) -> Transaction:
    """Сохраняет расход. Категория создаётся, если её нет."""
    with SessionLocal() as session:
        category = session.scalar(select(Category).where(Category.name == category_name))
        if category is None:
            category = Category(name=category_name)
            session.add(category)
            session.flush()
        tx = Transaction(
            user_id=user_id,
            category_id=category.id,
            amount=amount,
            description=description,
            spent_on=when or date.today(),
        )
        session.add(tx)
        session.commit()
        return tx


def month_summary(user_id: int, start: date, end: date) -> list[tuple[str, int]]:
    """Итоги по категориям за период [start, end): список (категория, сумма)."""
    with SessionLocal() as session:
        rows = session.execute(
            select(Category.name, func.sum(Transaction.amount))
            .join(Transaction, Transaction.category_id == Category.id)
            .where(Transaction.user_id == user_id, Transaction.spent_on >= start, Transaction.spent_on < end)
            .group_by(Category.name)
            .order_by(func.sum(Transaction.amount).desc())
        ).all()
    return [(name, int(total or 0)) for name, total in rows]


def month_total(user_id: int, start: date, end: date) -> int:
    """Общая сумма расходов пользователя за период."""
    with SessionLocal() as session:
        total = session.scalar(
            select(func.sum(Transaction.amount)).where(
                Transaction.user_id == user_id,
                Transaction.spent_on >= start,
                Transaction.spent_on < end,
            )
        )
    return int(total or 0)


def current_month_range(today: date | None = None) -> tuple[date, date]:
    """Границы текущего месяца [start, end)."""
    today = today or date.today()
    start = today.replace(day=1)
    end = date(start.year + 1, 1, 1) if start.month == 12 else date(start.year, start.month + 1, 1)
    return start, end


def set_budget(user_id: int, amount: int) -> None:
    """Задаёт месячный лимит бюджета."""
    with SessionLocal() as session:
        user = session.get(User, user_id)
        if user is not None:
            user.monthly_budget = amount
            session.commit()


def get_budget(user_id: int) -> int | None:
    """Возвращает месячный лимит бюджета пользователя."""
    with SessionLocal() as session:
        user = session.get(User, user_id)
        return user.monthly_budget if user else None


def budget_remaining(user_id: int, start: date, end: date) -> int | None:
    """Остаток бюджета за период: лимит минус уже потраченное. None — бюджет не задан."""
    budget = get_budget(user_id)
    if budget is None:
        return None
    return budget - month_total(user_id, start, end)


def update_transaction_category(tx_id: int, category_name: str) -> None:
    """Меняет категорию существующей транзакции (правка пользователя)."""
    with SessionLocal() as session:
        category = session.scalar(select(Category).where(Category.name == category_name))
        if category is None:
            category = Category(name=category_name)
            session.add(category)
            session.flush()
        tx = session.get(Transaction, tx_id)
        if tx is not None:
            tx.category_id = category.id
            session.commit()


def get_transaction(tx_id: int) -> Transaction | None:
    """Возвращает транзакцию по id (для правки категории)."""
    with SessionLocal() as session:
        return session.get(Transaction, tx_id)


# Стоп-слова: не используются при обучении категориям (глаголы ввода, предлоги, валюты)
_STOPWORDS = frozenset(
    "в на за и с о по из у для от до к купил купила купили купил(а) потратил "
    "потратила потратили заплатил заплатила сегодня вчера надо рублей рубля "
    "руб р рублів гривен гривны грн".split()
)


def rule_keyword(text: str) -> str:
    """Значимые слова текста (нижний регистр, без стоп-слов и чисел), через пробел.

    Используется для «обучения на правках»: если в новом тексте встречается
    хотя бы одно значимое слово из запомненного правила — применяем категорию.
    """
    import re

    words = re.findall(r"[а-яёa-z]+", (text or "").lower())
    significant = [w for w in words if w not in _STOPWORDS]
    seen: set[str] = set()
    unique = []
    for word in significant:
        if word not in seen:
            seen.add(word)
            unique.append(word)
    return " ".join(unique)


def remember_category_rule(user_id: int, description: str, category: str) -> None:
    """Запоминает правило «описание → категория» (обучение на правках)."""
    keyword = rule_keyword(description)
    if not keyword:
        return
    with SessionLocal() as session:
        existing = session.scalar(
            select(CategoryRule).where(
                CategoryRule.user_id == user_id,
                CategoryRule.keyword == keyword,
            )
        )
        if existing is not None:
            existing.category = category
        else:
            session.add(CategoryRule(user_id=user_id, keyword=keyword, category=category))
        session.commit()


def find_category_rule(user_id: int, text: str) -> str | None:
    """Возвращает запомненную категорию, если текст пересекается с правилом."""
    words = rule_keyword(text).split()
    if not words:
        return None
    with SessionLocal() as session:
        rules = session.scalars(
            select(CategoryRule).where(CategoryRule.user_id == user_id)
        ).all()
    wanted = set(words)
    for rule in rules:
        if wanted & set(rule.keyword.split()):
            return rule.category
    return None


def export_transactions(user_id: int, start: date, end: date) -> list[tuple[str, str, str, int]]:
    """Данные для экспорта: (дата, категория, описание, сумма) за период."""
    with SessionLocal() as session:
        rows = session.execute(
            select(Transaction.spent_on, Category.name, Transaction.description, Transaction.amount)
            .join(Category, Transaction.category_id == Category.id)
            .where(Transaction.user_id == user_id, Transaction.spent_on >= start, Transaction.spent_on < end)
            .order_by(Transaction.spent_on)
        ).all()
    return [(str(spent_on), category, description, amount) for spent_on, category, description, amount in rows]


def user_reset_summary(user_id: int) -> dict:
    """Сводка данных пользователя для предпросмотра перед сбросом (/reset)."""
    with SessionLocal() as session:
        tx_count, tx_sum = session.execute(
            select(func.count(Transaction.id), func.sum(Transaction.amount)).where(
                Transaction.user_id == user_id
            )
        ).one()
        rules_count = session.scalar(
            select(func.count(CategoryRule.id)).where(CategoryRule.user_id == user_id)
        ) or 0
        user = session.get(User, user_id)
    return {
        "user_exists": user is not None,
        "transactions": int(tx_count or 0),
        "amount": int(tx_sum or 0),
        "rules": int(rules_count or 0),
        "budget": user.monthly_budget if user else None,
    }


def reset_user(user_id: int) -> dict:
    """Полный сброс данных пользователя: траты, правила обучения, бюджет и профиль.

    Категории по умолчанию остаются (они общие для всех пользователей).
    Возвращает сводку удалённого. Действие необратимо — вызывается только
    после явного подтверждения пользователем.
    """
    with SessionLocal() as session:
        tx_count, tx_sum = session.execute(
            select(func.count(Transaction.id), func.sum(Transaction.amount)).where(
                Transaction.user_id == user_id
            )
        ).one()
        rules_count = session.scalar(
            select(func.count(CategoryRule.id)).where(CategoryRule.user_id == user_id)
        ) or 0
        user = session.get(User, user_id)
        budget = user.monthly_budget if user else None

        session.execute(delete(Transaction).where(Transaction.user_id == user_id))
        session.execute(delete(CategoryRule).where(CategoryRule.user_id == user_id))
        if user is not None:
            session.delete(user)
        session.commit()

    return {
        "transactions": int(tx_count or 0),
        "amount": int(tx_sum or 0),
        "rules": int(rules_count or 0),
        "budget": budget,
    }