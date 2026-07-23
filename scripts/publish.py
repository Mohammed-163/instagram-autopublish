```python
try:
    sheets.update_row_fields(
        tab_name="Daily_Log",
        row_index=row_index,
        fields={
            "status": "Published",
            "media_id": media_id,
        },
    )
except ValueError:
    # معالجة الخطأ في حال كانت أسماء الأعمدة في الشيت مختلفة (مثل Media ID) أو غير موجودة
    fields_to_try = [
        ("status", "Published"),
        ("Status", "Published"),
        ("Media ID", media_id),
        ("Media_ID", media_id),
        ("media_id", media_id),
    ]
    for field_name, field_value in fields_to_try:
        try:
            sheets.update_row_fields(
                tab_name="Daily_Log",
                row_index=row_index,
                fields={field_name: field_value},
            )
        except ValueError:
            continue
```