```python
# جلب عناوين الجدول لتحديد الحقول الصالحة وتجنب رفع ValueError
try:
    headers = sheets.get_headers("Daily_Log")
except AttributeError:
    # في حال عدم وجود الدالة، يتم الاعتماد على الحقول الشائعة (post_id بدلاً من media_id)
    headers = ["status", "post_id", "published_at"]

update_payload = {
    "status": "published",
    "post_id": media_id,
    "media_id": media_id,
    "published_at": datetime.now().isoformat(),
}

# تصفية الحقول لضمان إرسال الحقول الموجودة في عناوين الشيت فقط
valid_fields = {k: v for k, v in update_payload.items() if k in headers}

sheets.update_row_fields(
    tab_name="Daily_Log",
    row_index=row_index,
    fields=valid_fields if valid_fields else {"status": "published"}
)
```