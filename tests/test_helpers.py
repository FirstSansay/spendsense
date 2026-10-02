"""Юнит-тесты чистых функций: парсинг сумм/дат, нормализация позиций чеков.

Запускаются без сети: проверяются только вычисления, без вызовов AI API.
"""

import unittest
from datetime import date

from ai_service import _receipt_item_amount, extract_amount
from handlers.common import md_to_html, parse_amount, parse_date
from handlers.receipts import _clean_items, _looks_like_receipt
from sheets_service import build_values, sheet_title


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


class TestSheetValues(unittest.TestCase):
    """Матрица значений для Google Sheets (заголовок + строки)."""

    def test_build_values(self) -> None:
        rows = [("2026-10-01", "продукты", "хлеб", 45), ("2026-10-02", "транспорт", "бензин", 300)]
        values = build_values(rows)
        self.assertEqual(values[0], ["дата", "категория", "описание", "сумма"])
        self.assertEqual(len(values), 3)
        self.assertEqual(values[1], ["2026-10-01", "продукты", "хлеб", "45"])

    def test_build_values_empty(self) -> None:
        self.assertEqual(build_values([]), [["дата", "категория", "описание", "сумма"]])


class TestMdToHtml(unittest.TestCase):
    """Конвертация Markdown-фрагментов ответов ИИ в Telegram HTML."""

    def test_bold_italic_and_bullets(self) -> None:
        src = "- **Сократите «прочее» (9800 ₽).**\n- *Совет* ниже\n- **Итог**: 100 & 200"
        out = md_to_html(src)
        self.assertIn("<b>Сократите «прочее» (9800 ₽).</b>", out)
        self.assertIn("<i>Совет</i>", out)
        self.assertIn("<b>Итог</b>", out)
        self.assertIn("&amp;", out)  # спецсимволы экранированы
        self.assertTrue(out.startswith("• "))

    def test_plain_text_unchanged(self) -> None:
        src = "Просто текст без разметки."
        self.assertEqual(md_to_html(src), "Просто текст без разметки.")

    def test_special_chars_escaped(self) -> None:
        self.assertEqual(md_to_html("3 < 5 & 7"), "3 &lt; 5 &amp; 7")


class TestSheetTitle(unittest.TestCase):
    """Безопасное имя листа для пользователя (раздельный учёт)."""

    def test_username(self) -> None:
        self.assertEqual(sheet_title("alex_che", "Alex", 42), "alex_che")

    def test_fallback_to_first_name(self) -> None:
        self.assertEqual(sheet_title(None, "Alex Che", 42), "Alex Che")

    def test_fallback_to_user_id(self) -> None:
        self.assertEqual(sheet_title(None, None, 424242), "user_424242")

    def test_forbidden_characters_sanitized(self) -> None:
        self.assertEqual(sheet_title("a/b:c", "x", 1), "a_b_c")
        self.assertEqual(sheet_title("[bad]?*", "x", 1), "bad")

    def test_empty_title_sanitized(self) -> None:
        self.assertEqual(sheet_title("///", "///", 7), "user_7")


if __name__ == "__main__":
    unittest.main()