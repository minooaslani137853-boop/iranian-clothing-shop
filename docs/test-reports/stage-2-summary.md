# گزارش مرحله ۲

- تاریخ: ۲۰ آبان ۱۴۰۵ (۱۰ نوامبر ۲۰۲۶)
- Python 3.12.14، pytest 8.4.2، SQLAlchemy 2.0.44
- دستور: `python -m pytest tests/unit --html=docs/test-reports/stage-2.html --self-contained-html --junitxml=docs/test-reports/stage-2.xml`
- نتیجه نهایی: **۲۳ passed**، بدون failure، error یا skip؛ کد خروج ۰.
- پوشش: schema واقعی SQLite، قیود عدد صحیح و مقدار مثبت، کلید مرکب و یکتا، foreign key در اتصال تازه، cascade و restrict، snapshot نام و قیمت، پیش‌فرض‌های امن، جداسازی برنامه‌ها و init-db تکرارپذیر با ماندگاری داده در فایل.
- در اجرای نخست نام قید Boolean با قرارداد نام‌گذاری سازگار نبود؛ اصلاح شد و اجرای کامل مجدد موفق بود.
- این تست‌ها سطح مدل را با دیتابیس واقعی بررسی می‌کنند، نه mock. رابط HTTP و Selenium در این مرحله اجرا نشده‌اند.
- XML اجرای نهایی در همین پوشه ثبت شده؛ HTML محلی تولید می‌شود. داده‌های تست ساختگی‌اند.
