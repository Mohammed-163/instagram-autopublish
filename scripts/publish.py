```python
sheets.update_row_fields(
    tab_name="Daily_Log",
    row_number=row_number,
    fields={
        "Status": "Published",
        "Media ID": media_id,
    },
)
```