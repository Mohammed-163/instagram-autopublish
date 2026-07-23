```python
# تحديد مسميات الأعمدة بمرونة لتفادي اختلاف التسمية في جدول Daily_Log
try:
    headers = sheets.get_headers("Daily_Log")
except AttributeError:
    headers = []

media_id_key = next(
    (h for h in headers if h.strip().lower() in ["media id", "media_id", "ig_media_id", "post id"]),
    "Media ID"
)
status_key = next(
    (h for h in headers if h.strip().lower() in ["status", "state"]),
    "Status"
)

sheets.update_row_fields(
    tab_name="Daily_Log",
    row_index=row_index,
    fields={
        status_key: "Published",
        media_id_key: media_id,
    },
)
```