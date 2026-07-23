```python
sheets.update_row_fields(
    tab_name="Daily_Log",
    row_index=row_index,
    fields={
        "status": "published",
        "published_at": published_at,
        "post_id": media_id,
        "post_url": post_url,
    },
)
```