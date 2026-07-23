```python
sheets.update_row_fields(
    "Daily_Log",
    row_index,
    {
        "status": "published",
        "ig_media_id": media_id,
        "published_at": published_at,
    },
)
```