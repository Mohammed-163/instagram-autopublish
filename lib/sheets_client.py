"""
Google Sheets wrapper (gspread) — the system's shared database.
Every method is defensive: it lets exceptions propagate with clear messages
so the calling script's error_handler can classify and act on them.
"""
import json
from datetime import datetime, timedelta

import gspread
from google.oauth2.service_account import Credentials

from . import config

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class SheetsClient:
    def __init__(self, service_account_json: str, sheet_id: str):
        info = json.loads(service_account_json)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        self.gc = gspread.authorize(creds)
        self.sheet = self.gc.open_by_key(sheet_id)

    def _ws(self, tab_name: str):
        return self.sheet.worksheet(tab_name)

    # -- System control -----------------------------------------------------
    def check_system_status(self) -> str:
        try:
            ws = self._ws(config.SYSTEM_CONTROL_TAB)
            value = ws.acell("B1").value
            return (value or config.SYSTEM_STATUS_ACTIVE).strip().lower()
        except gspread.exceptions.WorksheetNotFound:
            # If the control tab doesn't exist yet, default to active
            return config.SYSTEM_STATUS_ACTIVE

    def is_paused(self) -> bool:
        return self.check_system_status() == config.SYSTEM_STATUS_PAUSED

    # -- Plan -----------------------------------------------------------------
    def get_today_plan(self, date_str: str) -> dict | None:
        ws = self._ws(config.CURRENT_PLAN_TAB)
        records = ws.get_all_records()
        for row in records:
            if str(row.get("date")) == date_str:
                return row
        return None

    def read_current_plan_rows(self) -> list:
        ws = self._ws(config.CURRENT_PLAN_TAB)
        return ws.get_all_values()[1:]  # skip header row

    def archive_and_reset_plan(self, new_plan_rows: list, month_label: str) -> None:
        current = self._ws(config.CURRENT_PLAN_TAB)
        history = self._ws(config.PLAN_HISTORY_TAB)

        old_rows = current.get_all_values()[1:]
        if old_rows:
            archived = [row + [month_label] for row in old_rows]
            history.append_rows(archived, value_input_option="RAW")

        # clear everything except header row
        current.batch_clear(["A2:Z1000"])
        if new_plan_rows:
            current.append_rows(new_plan_rows, value_input_option="RAW")

    # -- Daily log --------------------------------------------------------------
    def get_recent_topics(self, n: int = config.TOPIC_HISTORY_LOOKBACK) -> list:
        ws = self._ws(config.DAILY_LOG_TAB)
        records = ws.get_all_records()
        return [r.get("topic_slug", "") for r in records[-n:] if r.get("topic_slug")]

    def append_daily_log(self, row: dict) -> None:
        ws = self._ws(config.DAILY_LOG_TAB)
        ordered = [row.get(h, "") for h in config.DAILY_LOG_HEADERS]
        ws.append_row(ordered, value_input_option="RAW")

    def get_ready_posts_due_now(self, now_iso: str) -> list:
        """Returns list of (row_index, row_dict) for posts ready to publish."""
        ws = self._ws(config.DAILY_LOG_TAB)
        records = ws.get_all_records()
        due = []
        for idx, row in enumerate(records, start=2):  # +2: header row + 1-indexing
            if row.get("status") == config.STATUS_READY and row.get("scheduled_time", "") <= now_iso:
                due.append((idx, row))
        return due

    def get_published_for_cleanup(self, cutoff_hours: int = config.CLEANUP_DELAY_HOURS) -> list:
        ws = self._ws(config.DAILY_LOG_TAB)
        records = ws.get_all_records()
        cutoff = datetime.utcnow() - timedelta(hours=cutoff_hours)
        due = []
        for idx, row in enumerate(records, start=2):
            if row.get("status") != config.STATUS_PUBLISHED:
                continue
            pub_at = row.get("published_at", "")
            if not pub_at:
                continue
            try:
                pub_dt = datetime.fromisoformat(pub_at)
            except ValueError:
                continue
            if pub_dt <= cutoff:
                due.append((idx, row))
        return due

    def update_row_field(self, tab_name: str, row_index: int, field_name: str, value) -> None:
        ws = self._ws(tab_name)
        headers = ws.row_values(1)
        if field_name not in headers:
            raise ValueError(f"Field '{field_name}' not found in {tab_name} headers")
        col = headers.index(field_name) + 1
        ws.update_cell(row_index, col, value)

    # -- Backup -----------------------------------------------------------------
    def export_tab_csv(self, tab_name: str) -> str:
        import csv
        import io
        ws = self._ws(tab_name)
        rows = ws.get_all_values()
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerows(rows)
        return buf.getvalue()
