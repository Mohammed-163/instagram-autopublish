```python
# استعلام عن رؤوس الأعمدة لتحديد المسمى الصحيح للحقل وتفادي الخطأ
headers = sheets.get_headers("Daily_Log") if hasattr(sheets, "get_headers") else []

# مطابقة اسم الحقل بناءً على ما هو موجود في الجدول (Media ID أو media_id)
media_key = None
if "Media ID" in headers:
    media_key = "Media ID"
elif "media_id" in headers:
    media_key = "media_id"

update_fields = {}
if "status" in headers:
    update_fields["status"] = "published"
elif "Status" in headers:
    update_fields["Status"] = "published"

if media_key:
    update_fields[media_key] = media_id

# التحديث فقط بالحقول الموجودة بالفعل في رأس الجدول
if update_fields:
    sheets.update_row_fields(
        tab_name="Daily_Log",
        row_index=row_index,
        fields=update_fields
    )
else:
    # محاولة التحديث بالاسم الشائع "Media ID" في حال تعذر قراءة الرؤوس مباشرة
    try:
        sheets.update_row_fields(
            tab_name="Daily_Log",
            row_index=row_index,
            fields={"Media ID": media_id, "status": "published"}
        )
    except ValueError:
        sheets.update_row_fields(
            tab_name="Daily_Log",
            row_index=row_index,
            fields={"status": "published"}
        )
```