```python
# الحصول على رؤوس الأعمدة المتاحة لتفادي خطأ الكلمات المفتاحية المفقودة
headers = sheets.get_headers("Daily_Log")

# تجهيز حقول التحديث الأساسية
update_fields = {
    "status": status,
    "published_at": published_at,
    "error_message": error_message if 'error_message' in locals() else ""
}

# مطابقة معرّف الميديا مع اسم العمود الموجود في الشيت
if 'media_id' in locals() and media_id:
    for candidate in ["media_id", "ig_media_id", "post_id", "id"]:
        if candidate in headers:
            update_fields[candidate] = media_id
            break

# تصفية الحقول لضمان إرسال الأعمدة الموجودة بالفعل في الهيدر فقط
valid_fields = {k: v for k, v in update_fields.items() if k in headers}

# تحديث الصف بالحقول الصالحة
sheets.update_row_fields(
    tab_name="Daily_Log",
    row_num=row_num,
    fields=valid_fields
)
```