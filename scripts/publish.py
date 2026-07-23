```python
# جلب عناوين الأعمدة المتوفرة في ورقة Daily_Log لتفادي استدعاء حقول غير موجودة
headers = sheets.get_headers("Daily_Log") if hasattr(sheets, "get_headers") else []

# تجهيز البيانات المراد تحديثها
payload = {
    "status": "Published",
    "media_id": media_id,
}

# تصفية الحقول لتشمل فقط الأعمدة الموجودة بالفعل في شيت Daily_Log
# ودعم الاختلافات الشائعة للأسماء مثل (media_id أو Media ID)
filtered_fields = {}
for key, value in payload.items():
    if key in headers:
        filtered_fields[key] = value
    else:
        matched_header = next((h for h in headers if h.lower().replace(" ", "_") == key.lower()), None)
        if matched_header:
            filtered_fields[matched_header] = value

if filtered_fields:
    sheets.update_row_fields(
        tab_name="Daily_Log",
        row_index=row_index,
        fields=filtered_fields
    )
```