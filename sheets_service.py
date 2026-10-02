"""Экспорт расходов в Google Sheets через Service Account.

В итоговой таблице каждому пользователю соответствует ОТДЕЛЬНЫЙ лист
(имя — username или «user_<id>»). При каждом экспорте лист пользователя
полностью перезаписывается: заголовок + все его расходы. Это исключает
дубликаты строк при повторных экспортах.

Учётные данные — JSON-ключ Service Account (google-auth), доступ к таблице
даётся по email этого аккаунта («Настройки доступа» в Google Sheets).
"""

import json
import re

from google.auth import load_credentials_from_dict
from googleapiclient.discovery import build

import config

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Символы, запрещённые в именах листов Google Sheets
_INVALID_SHEET_CHARS = re.compile(r"[\[\]:*?/\\\x00-\x1f]")


def sheet_title(username: str | None, first_name: str | None, user_id: int) -> str:
    """Безопасное имя листа для пользователя: username, иначе first_name, иначе user_<id>.

    Google Sheets: имя до 100 символов, нельзя [' ] : * ? / \\  и пустые имена.
    """
    base = (username or first_name or "")[:50]
    base = _INVALID_SHEET_CHARS.sub("_", base).strip(" _.")
    return base or f"user_{user_id}"


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


def _ensure_sheet(service, spreadsheet_id: str, title: str) -> tuple[bool, str]:
    """Проверяет наличие листа с именем title; при отсутствии — создаёт."""
    meta = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id, fields="sheets.properties.title"
    ).execute()
    titles = {s.get("properties", {}).get("title") for s in meta.get("sheets", [])}
    if title in titles:
        return True, ""
    body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
    return True, "лист создан"


def export_user_sheet(
    spreadsheet_id: str,
    title: str,
    rows: list[tuple[str, str, str, int]],
) -> tuple[bool, str]:
    """Записывает расходы пользователя в его лист (перезапись).

    Создаёт лист, если его нет; очищает его и пишет заголовок + все расходы.
    Возвращает (успех, сообщение).
    """
    try:
        creds = get_credentials()
        service = build("sheets", "v4", credentials=creds)
        ok, detail = _ensure_sheet(service, spreadsheet_id, title)
        if not ok:
            return False, detail

        values_api = service.spreadsheets().values()
        # Очистка листа — убираем остатки от предыдущих экспортов
        values_api.clear(
            spreadsheetId=spreadsheet_id, range=f"{title}!A:Z", body={}
        ).execute()
        # Запись заголовка и всех расходов
        values_api.update(
            spreadsheetId=spreadsheet_id,
            range=f"{title}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": build_values(rows), "majorDimension": "ROWS"},
        ).execute()
        return True, f"строк: {len(rows) + 1} (заголовок + {len(rows)})"
    except Exception as exc:  # нет ключа, нет сети, недостаточно прав и т.п.
        return False, str(exc)