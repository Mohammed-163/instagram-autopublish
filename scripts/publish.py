```python
# جلب عناوين الأعمدة المتاحة في ورقة Daily_Log لتفادي خطأ عدم وجود العمود
log_headers = sheets.get_headers("Daily_Log")

# إعداد البيانات المراد تحديثها
log_data = {
    "Status": "Published",
    "media_id": media_id,
}

# دعم المسميات المختلفة لعمود معرف الوسائط إن وجدت (مثل Media_ID أو ID)
if "media_id" not in log_headers:
    if "Media_ID" in log_headers:
        log_data["Media_ID"] = log_data.pop("media_id")
    elif "Media ID" in log_headers:
        log_data["Media ID"] = log_data.pop("media_id")

# تصفية الحقول بحيث يتم إرسال الحقول الموجودة بالفعل فقط في الهيدر
update_fields = {k: v for k, v in log_data.items() if k in log_headers}

sheets.update_row_fields(
    tab_name="Daily_Log",
    row_index=row_index,
    fields=update_fields
)
```