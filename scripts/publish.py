```python
update_fields = {
    "status": "published",
    "published_at": published_at,
    "media_id": media_id
}

try:
    sheets.update_row_fields(
        tab_name="Daily_Log",
        row_index=row_index,
        fields=update_fields
    )
except ValueError as e:
    if "media_id" in str(e):
        update_fields.pop("media_id", None)
        sheets.update_row_fields(
            tab_name="Daily_Log",
            row_index=row_index,
            fields=update_fields
        )
    else:
        raise e
```