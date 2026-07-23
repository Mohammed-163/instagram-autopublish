```python
sheets.update_row_fields(
    tab_name="Daily_Log",
    row_index=row_index,
    fields={
        "Status": "PUBLISHED",
        "Media ID": media_id,
    }
)
```