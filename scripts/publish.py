```python
# تحديث الحقول بشكل آمن ومطابقة اسم العمود في الشيت (Media ID بدلاً من media_id)
update_payload = {
    "status": "published",
    "Media ID": media_id  # تغيير المسمى ليطابق الهيدر في Daily_Log
}

for field_name, field_value in update_payload.items():
    try:
        sheets.update_row_fields(
            tab_name="Daily_Log",
            row_index=row_index,
            fields={field_name: field_value}
        )
    except ValueError:
        # التجاوز في حال عدم وجود العمود لتفادي إيقاف التحديث
        continue
```