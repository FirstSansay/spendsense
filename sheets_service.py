"""Экспорт расходов в Google Sheets через Service Account.

Учётные данные — JSON-ключ Service Account (google-auth), доступ к таблице
даётся по email этого аккаунта («Настройки доступа» в Google Sheets).
Данные дописываются в конец листа; заголовок создаётся при первом экспорте.
"""

import json

from google.auth import load_credentials_from_dict
from googleapiclient.discovery import build

import config

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_credentials():
    """Учётные данные Service Account: JSON-строка из env или файл на диске."""
    if config.GOOGLE_CREDENTIALS_JSON:
        info = json.loads(config.GOOGLE_CREDENTIALS_JSON)
    else:
        with open(config.GOOGLE_CREDENTIALS_PATH, "r", encoding="utf-8") as file:
            info = json.load(file)
    credentials, _project = load_credentials_from_dict(info, scopes=SCOPES)
    return credentials


def build_values(rows: list[tuple[str, str, str, int]]) -> list[list[str]]:
    """Матрица значений для таблицы: заголовок + строки (дата, категория, описание, сумма)."""
    values: list[list[str]] = [["дата", "категория", "описание", "сумма"]]
    for spent_on, category, description, amount in rows:
        values.append([spent_on, category, description, str(amount)])
    return values


def _first_sheet_title(service, spreadsheet_id: str) -> str:
    """Имя первой вкладки таблицы (не зависит от локали: Sheet1 / Лист1)."""
    try:
        meta = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id, fields="sheets.properties.title"
        ).execute()
        for sheet in meta.get("sheets", []):
            title = sheet.get("properties", {}).get("title")
            if title:
                return title
    except Exception:
        pass
    return config.GOOGLE_SHEET_RANGE


def export_month(spreadsheet_id: str, rows: list[tuple[str, str, str, int]]) -> tuple[bool, str]:
    """Записывает расходы в Google Sheets. Возвращает (успех, сообщение).

    Если в листе ещё нет заголовка — создаём его вместе с данными,
    иначе дописываем строки в конец.
    """
    try:
        creds = get_credentials()
        service = build("sheets", "v4", credentials=creds)
        values_api = service.spreadsheets().values()
        sheet = _first_sheet_title(service, spreadsheet_id)

        # Проверяем, есть ли уже заголовок в A1
        existing = values_api.get(
            spreadsheetId=spreadsheet_id, range=f"{sheet}!A1:D1"
        ).execute().get("values") or []
        has_header = bool(existing) and existing[0] and existing[0][0] == "дата"

        body = {
            "values": build_values(rows) if not has_header else build_values(rows)[1:],
            "majorDimension": "ROWS",
        }
        result = values_api.append(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet}!A1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body,
        ).execute()
        updated = result.get("updates", {}).get("updatedRows", 0)
        return True, f"дописано строк: {updated}"
    except Exception as exc:  # нет ключа, нет сети, недостаточно прав и т.п.
        return False, str(exc)