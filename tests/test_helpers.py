"""Юнит-тесты чистых функций: парсинг сумм/дат, нормализация позиций чеков.

Запускаются без сети: проверяются только вычисления, без вызовов AI API.
"""

import unittest
from datetime import date

from ai_service import _receipt_item_amount, extract_amount
from handlers.common import parse_amount, parse_date
from handlers.receipts import _clean_items, _looks_like_receipt


class TestParseAmount(unittest.TestCase):
    """Перевод суммы из ответа ИИ в целое число рублей."""

    def test_cases(self) -> None:
        self.assertEqual(parse_amount(250), 250)
        self.assertEqual(parse_amount("250"), 250)
        self.assertEqual(parse_amount(250.7), 251)  # округление
        self.assertEqual(parse_amount("90.90"), 91)
        self.assertEqual(parse_amount(" 450 "), 450)
        self.assertIsNone(parse_amount("дальше некуда"))
        self.assertIsNone(parse_amount(None))
        self.assertIsNone(parse_amount(""))


class TestParseDate(unittest.TestCase):
    """Дата из ответа ИИ; при ошибке — сегодня."""

    def test_valid(self) -> None:
        self.assertEqual(parse_date("2026-10-05"), date(2026, 10, 5))

    def test_invalid_falls_back_to_today(self) -> None:
        self.assertEqual(parse_date("05.10.2026"), date.today())
        self.assertEqual(parse_date(None), date.today())
        self.assertEqual(parse_date("ccc"), date.today())


class TestReceiptItemAmount(unittest.TestCase):
    """Страховочный пересчёт итога строки с количеством/весом."""

    def test_cases(self) -> None:
        cases = [
            # (позиция от ИИ, ожидаемый итог)
            ({"amount": 120, "description": "молоко 2*120"}, 240),
            ({"amount": 199, "description": "мандарины 0.450кг*199.90"}, 90),
            ({"amount": 240, "description": "молоко 2*120"}, 240),  # уже итог
            ({"amount": 90, "description": "мандарины 0.450кг*199.90"}, 90),
            ({"amount": 45, "description": "хлеб"}, 45),  # без количества
            ({"amount": 45, "description": "молоко 3х15"}, 45),  # 3×15=45
            ({"amount": "?!", "description": "хлеб"}, None),  # битая сумма
        ]
        for item, expected in cases:
            self.assertEqual(_receipt_item_amount(item), expected, msg=str(item))


class TestCleanItems(unittest.TestCase):
    """Фильтрация позиций чека."""

    def test_filters_invalid(self) -> None:
        items = [
            {"amount": 45, "category": "продукты", "description": "хлеб"},
            {"amount": 0, "category": "продукты", "description": "ноль"},
            {"amount": None, "category": "продукты", "description": "битое"},
            {"amount": -5, "category": "продукты", "description": "минус"},
            "не-словарь",
        ]
        cleaned = _clean_items(items)
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0]["amount"], 45)

    def test_quantity_added_to_description(self) -> None:
        items = [
            {"amount": 240, "quantity": 2, "category": "продукты", "description": "молоко"},
            {"amount": 240, "quantity": 2, "category": "продукты", "description": "кефир 2*120"},
            {"amount": 90, "quantity": 0.45, "category": "продукты", "description": "мандарины"},
        ]
        cleaned = _clean_items(items)
        self.assertEqual(cleaned[0]["description"], "2× молоко")
        self.assertEqual(cleaned[1]["description"], "кефир 2*120")  # уже есть паттерн
        self.assertEqual(cleaned[2]["description"], "0.45× мандарины")

    def test_quantity_one_not_added(self) -> None:
        items = [{"amount": 45, "quantity": 1, "category": "продукты", "description": "хлеб"}]
        cleaned = _clean_items(items)
        self.assertEqual(cleaned[0]["description"], "хлеб")


class TestLooksLikeReceipt(unittest.TestCase):
    """Эвристика «текст похож на чек»."""

    def test_cases(self) -> None:
        self.assertTrue(_looks_like_receipt("МАГНИТ КАССА\nМОЛОКО 89.90\nИТОГО 413.90"))
        self.assertFalse(_looks_like_receipt("короткий текст"))
        self.assertFalse(_looks_like_receipt("213123123123"))
        self.assertFalse(_looks_like_receipt(""))


class TestExtractAmount(unittest.TestCase):
    """Извлечение первого числа как суммы (путь без ИИ, правила категорий)."""

    def test_cases(self) -> None:
        self.assertEqual(extract_amount("250 кофе"), 250)
        self.assertEqual(extract_amount("купил продукты на 870"), 870)
        self.assertEqual(extract_amount("такси 450"), 450)
        self.assertEqual(extract_amount("2.5 кг огурцов 200"), 2)  # дробь — целая часть
        self.assertEqual(extract_amount("без суммы"), None)
        self.assertEqual(extract_amount(""), None)
        self.assertEqual(extract_amount(None), None)


if __name__ == "__main__":
    unittest.main()