import re
import time
import logging

from googleapiclient.errors import HttpError

from config import SPREADSHEET_ID


def _sheets_call_with_retry(fn, retries=3):
    for attempt in range(retries):
        try:
            return fn()
        except HttpError as e:
            if e.resp.status in (429, 500, 503) and attempt < retries - 1:
                wait = (2 ** attempt) * 2
                logging.warning(f"Sheets API {e.resp.status}, retry {attempt+1}/{retries-1} in {wait}s...")
                time.sleep(wait)
            else:
                raise
        except (TimeoutError, OSError) as e:
            if attempt < retries - 1:
                wait = (2 ** attempt) * 2
                logging.warning(f"Sheets API timeout, retry {attempt+1}/{retries-1} in {wait}s...")
                time.sleep(wait)
            else:
                raise


def col_letter(col_1based: int) -> str:
    result = ""
    n = col_1based
    while n > 0:
        n, r = divmod(n - 1, 26)
        result = chr(65 + r) + result
    return result


def make_range(sheet_name: str, row: int, col: int) -> str:
    return f"'{sheet_name}'!{col_letter(col)}{row}"


def cell_value(row: list, col_1based: int) -> str:
    idx = col_1based - 1
    return str(row[idx]).strip() if idx < len(row) else ""


def read_sheet(sheets_service, sheet_name: str) -> list:
    result = _sheets_call_with_retry(lambda: sheets_service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{sheet_name}'!A:Y",
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute())
    return result.get("values", [])


def batch_write(sheets_service, updates: list, chunk_size: int = 100):
    if not updates:
        return
    for i in range(0, len(updates), chunk_size):
        chunk = updates[i:i + chunk_size]
        _sheets_call_with_retry(lambda c=chunk: sheets_service.spreadsheets().values().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={"valueInputOption": "USER_ENTERED", "data": c},
        ).execute())


def get_all_batch_sheet_names(sheets_service) -> list:
    spreadsheet = _sheets_call_with_retry(lambda: sheets_service.spreadsheets().get(
        spreadsheetId=SPREADSHEET_ID
    ).execute())
    all_sheets = [s["properties"]["title"] for s in spreadsheet["sheets"]]
    return [s for s in all_sheets if re.match(r"^Batch\s*\d+$", s, re.IGNORECASE)]
