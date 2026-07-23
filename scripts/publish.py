```python
# تحديث بيانات التقرير بشكل آمن لتجنب توقف السكربت إذا كان العمود غير موجود في الترويسة (Headers)
update_fields = {
    "status": "published",
    "media_id": media_id,
    "Media ID": media_id,
    "post_id": media_id
}

for field_key, field_value in update_fields.items():
    try:
        sheets.update_row_fields(
            tab_name="Daily_Log",
            row_index=row_index,
            fields={field_key: field_value}
        )
    except ValueError:
        # تجاهل الحقول غير الموجودة في ترويسة الجدول وتجاوز الخطأ
        continue
```