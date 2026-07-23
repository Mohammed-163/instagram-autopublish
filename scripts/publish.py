```python
try:
    sheets.update_row_fields(
        tab_name="Daily_Log",
        row_index=row_index,
        fields={
            "Status": "Published",
            "Media ID": media_id
        }
    )
except ValueError:
    try:
        sheets.update_row_fields(
            tab_name="Daily_Log",
            row_index=row_index,
            fields={
                "Status": "Published",
                "media_id": media_id
            }
        )
    except ValueError:
        sheets.update_row_fields(
            tab_name="Daily_Log",
            row_index=row_index,
            fields={
                "Status": "Published"
            }
        )
```