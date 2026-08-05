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

    def _ws_or_create(self, tab_name: str, headers: list):
        """Returns the worksheet, creating it with the given header row if it
        doesn't exist yet (used for the new Post_Performance tab so users
        don't have to manually create it in their Google Sheet)."""
        try:
            return self.sheet.worksheet(tab_name)
        except gspread.exceptions.WorksheetNotFound:
            ws = self.sheet.add_worksheet(title=tab_name, rows=1000, cols=len(headers) + 2)
            ws.append_row(headers, value_input_option="RAW")
            return ws

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

    def get_stale_publishing_rows(self, cutoff_minutes: int) -> list:
        """Rows stuck in status=publishing longer than cutoff_minutes — the
        reservation write succeeded but the confirm-publish step never came
        back (crash, runner killed, etc). We do NOT auto-retry these (the
        Instagram call may well have actually succeeded), we just surface
        them so a human can check Instagram and fix the sheet by hand."""
        ws = self._ws(config.DAILY_LOG_TAB)
        records = ws.get_all_records()
        cutoff = datetime.utcnow() - timedelta(minutes=cutoff_minutes)
        stale = []
        for idx, row in enumerate(records, start=2):
            if row.get("status") != config.STATUS_PUBLISHING:
                continue
            reserved_at = row.get("reserved_at", "")
            if not reserved_at:
                continue
            try:
                reserved_dt = datetime.fromisoformat(reserved_at)
            except ValueError:
                continue
            if reserved_dt <= cutoff:
                stale.append((idx, row))
        return stale

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
        """Kept for backwards compatibility; prefer update_row_fields for
        anything that updates more than one column (fewer API calls, smaller
        race window)."""
        self.update_row_fields(tab_name, row_index, {field_name: value})

    def update_row_fields(self, tab_name: str, row_index: int, field_values: dict,
                           verify_field: str = "topic_slug", verify_value: str | None = None) -> None:
        """Updates multiple columns of one row in a single batch call.

        Sheets has no row-level locking, so two workflow runs (e.g. publish.py
        firing every 15 min, or a person editing the sheet by hand) can shift
        row numbers between when we *read* a row and when we *write* to it.
        If verify_value is given, we re-read that cell right before writing
        and abort instead of silently corrupting a different row.
        """
        ws = self._ws(tab_name)
        headers = ws.row_values(1)
        for field_name in field_values:
            if field_name not in headers:
                raise ValueError(f"Field '{field_name}' not found in {tab_name} headers")

        if verify_value is not None:
            if verify_field not in headers:
                raise ValueError(f"Verify field '{verify_field}' not found in {tab_name} headers")
            verify_col = headers.index(verify_field) + 1
            current = ws.cell(row_index, verify_col).value
            if current != verify_value:
                raise RuntimeError(
                    f"Row {row_index} in {tab_name} shifted since it was read "
                    f"(expected {verify_field}='{verify_value}', found '{current}'). "
                    f"Skipping update to avoid corrupting the wrong row."
                )

        cell_list = []
        for field_name, value in field_values.items():
            col = headers.index(field_name) + 1
            cell_list.append(gspread.Cell(row=row_index, col=col, value=value))
        ws.update_cells(cell_list, value_input_option="RAW")

    # -- Post performance (fed to Gemini for monthly planning) ------------------
    def append_post_performance(self, row: dict) -> None:
        ws = self._ws_or_create(config.POST_PERFORMANCE_TAB, config.POST_PERFORMANCE_HEADERS)
        ordered = [row.get(h, "") for h in config.POST_PERFORMANCE_HEADERS]
        ws.append_row(ordered, value_input_option="RAW")

    def get_all_post_performance(self) -> list:
        ws = self._ws_or_create(config.POST_PERFORMANCE_TAB, config.POST_PERFORMANCE_HEADERS)
        return ws.get_all_records()

    def get_posts_due_for_insights(self, cutoff_iso: str) -> list:
        """Published posts whose published_at is older than cutoff_iso and
        that haven't had insights pulled yet. Also naturally catches posts
        that were missed in a previous run (insights_fetched still blank),
        regardless of how old they are."""
        ws = self._ws(config.DAILY_LOG_TAB)
        records = ws.get_all_records()
        due = []
        for idx, row in enumerate(records, start=2):
            if row.get("status") not in (config.STATUS_PUBLISHED, config.STATUS_CLEANED):
                continue
            if row.get("insights_fetched") == "yes":
                continue
            if not row.get("media_id"):
                continue
            published_at = row.get("published_at", "")
            if not published_at:
                continue
            if published_at <= cutoff_iso:
                due.append((idx, row))
        return due

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
