# استخدام صورة رسمية من مايكروسوفت تحتوي على بايثون وكل متطلبات Playwright
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# تحديد مسار العمل
WORKDIR /app

# نسخ ملف المتطلبات وتثبيت المكتبات
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# تثبيت متصفح كروميوم فقط لتخفيف الحجم
RUN playwright install chromium

# نسخ باقي ملفات البوت
COPY . .

# أمر تشغيل البوت
CMD ["python", "bot.py"]
