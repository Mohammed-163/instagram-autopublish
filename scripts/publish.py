```python
headers = sheets.get_headers("Daily_Log") if hasattr(sheets, "get_headers") else []

fields_to_update = {
    "status": "PUBLISHED",
    "media_id": media_id,
    "error": ""
}

# تصفية الحقول لتحديث الحقول الموجودة بالفعل في ترويسة الشيت لتجنب KeyError / ValueError
valid_fields = {k: v for k, v in fields_to_update.items() if k in headers} if headers else fields_to_update

if valid_fields:
    sheets.update_row_fields(
        tab_name="Daily_Log",
        row_index=row_index,
        fields=valid_fields
    )
```