"""Работа с базой данных: пользователи, категории, транзакции, бюджет.

Для MVP используется SQLite, далее возможен переход на PostgreSQL (config.DATABASE_URL).
"""

from datetime import date, datetime, timezone

from sqlalchemy import ForeignKey, create_engine, func, select
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