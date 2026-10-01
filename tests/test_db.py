"""Юнит-тесты слоя базы данных.

Запускаются без сети и ключей: используется отдельный SQLite-файл в /tmp.
"""

import os
import tempfile
import unittest
from datetime import date

# Подменяем БД ДО импорта модуля (config читает переменную окружения)
_TMP_DB = os.path.join(tempfile.gettempdir(), "spendsense_test.db")
for suffix in ("", "-journal"):
    path = _TMP_DB + suffix
    if os.path.exists(path):
        os.remove(path)
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"

import db  # noqa: E402


class TestDb(unittest.TestCase):
    def setUp(self) -> None:
        # Изолируем каждый тест: пересоздаём схему с нуля
        db.Base.metadata.drop_all(db.engine)
        db.init_db()

    def test_default_categories_created(self) -> None:
        """После init_db существуют все категории по умолчанию."""
        seen = set(db.DEFAULT_CATEGORIES)
        self.assertEqual(len(db.DEFAULT_CATEGORIES), 10)
        self.assertIn("прочее", seen)
        self.assertIn("продукты", seen)

    def test_get_or_create_user_idempotent(self) -> None:
        """Пользователь создаётся один раз; повторный запрос возвращает того же."""
        first = db.get_or_create_user(111, "tester", "Тест")
        second = db.get_or_create_user(111)
        self.assertEqual(first.id, second.id)
        self.assertEqual(first.username, "tester")

    def test_add_transaction_creates_unknown_category(self) -> None:
        """Неизвестная категория создаётся автоматически."""
        db.add_transaction(111, 250, "кофешоп", "латте", date.today())
        summary = db.month_summary(111, *db.current_month_range())
        names = [name for name, _ in summary]
        self.assertIn("кофешоп", names)

    def test_month_summary_and_total(self) -> None:
        """Сводка по категориям и общий итог за период считаются верно."""
        db.get_or_create_user(222, "u222")
        db.add_transaction(222, 100, "продукты", "хлеб", date.today())
        db.add_transaction(222, 50, "продукты", "молоко", date.today())
        db.add_transaction(222, 300, "транспорт", "бензин", date.today())

        start, end = db.current_month_range()
        summary = dict(db.month_summary(222, start, end))
        total = db.month_total(222, start, end)

        self.assertEqual(summary["продукты"], 150)
        self.assertEqual(summary["транспорт"], 300)
        self.assertEqual(total, 450)

    def test_month_total_ignores_others_periods(self) -> None:
        """Расходы за прошлый период не попадают в текущий месяц."""
        db.add_transaction(333, 999, "прочее", "старое", date(2000, 1, 15))
        start, end = db.current_month_range()
        self.assertEqual(db.month_total(333, start, end), 0)

    def test_budget_flow(self) -> None:
        """Установка бюджета и остаток за месяц."""
        db.get_or_create_user(222, "u222")
        db.add_transaction(222, 450, "транспорт", "бензин", date.today())
        db.set_budget(222, 1000)
        self.assertEqual(db.get_budget(222), 1000)
        start, end = db.current_month_range()
        remaining = db.budget_remaining(222, start, end)
        self.assertEqual(remaining, 1000 - 450)

    def test_budget_remaining_without_budget(self) -> None:
        """Без установленного бюджета остаток = None."""
        start, end = db.current_month_range()
        self.assertIsNone(db.budget_remaining(444, start, end))

    def test_current_month_range_december(self) -> None:
        """Границы декабря заканчиваются 1 января следующего года."""
        start, end = db.current_month_range(date(2026, 12, 15))
        self.assertEqual(start, date(2026, 12, 1))
        self.assertEqual(end, date(2027, 1, 1))


if __name__ == "__main__":
    unittest.main()