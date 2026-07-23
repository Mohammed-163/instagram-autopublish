```python
sheets.update_row_fields(
    tab_name="Daily_Log",
    row_num=row_num,
    fields={
        "status": "published",
        "ig_media_id": media_id,
    },
)
```