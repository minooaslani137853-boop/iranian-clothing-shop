# گزارش نهایی مرحله ۶

این گزارش از XML اجرای واقعی همین نوبت تولید شده است؛ شمارش‌ها دستی نیستند.

- شروع اجرا (Asia/Tehran): 2026-11-10T15:44:08.737317+03:30
- نسخه کد هنگام اجرا: `b7fd464da37d289c04404a38d01ab2638528a2c9` (تغییرات مرحله ۶ در working tree)
- فرمان قابل تکرار: `python scripts/run_test_reports.py`
- کد خروج pytest: **0**
- مرورگر واقعی: **Playwright headless / Chromium 156.0.8078.79**
- منبع جزئیات: [JUnit XML](stage-6.xml) و [گزارش HTML](stage-6.html).

## نتیجه همه انواع تست

| نوع | Passed | Failed | Error | Skipped | مجموع |
|---|---:|---:|---:|---:|---:|
| Unit | 23 | 0 | 0 | 0 | 23 |
| Integration | 92 | 0 | 0 | 0 | 92 |
| System | 1 | 0 | 0 | 0 | 1 |
| Acceptance | 3 | 0 | 0 | 0 | 3 |
| **کل** | 119 | 0 | 0 | 0 | 119 |

## اجرای مرورگر

هر تست سرور واقعی Werkzeug روی پورت آزاد loopback و دیتابیس فایل SQLite مستقل دارد. ابتدا پاسخ HTTP محصولات بررسی می‌شود؛ فرم‌ها از طریق مرورگر و CSRF واقعی ارسال می‌شوند. هیچ درخواست خرید با Flask test client در تست‌های System و Acceptance انجام نمی‌شود. در پایان سرور، اتصال دیتابیس، context و مرورگر بسته می‌شوند. داده‌های نام، ایمیل، تلفن و نشانی ساختگی‌اند و هیچ اطلاعات کارت دریافت یا ذخیره نمی‌شود. پرداخت واقعی بانکی اجرا نشده؛ پرداخت Mock واقعی برنامه اجرا شده است.

- `tests.acceptance.test_user_stories.test_us01_search_product`
- `tests.acceptance.test_user_stories.test_us02_add_to_cart`
- `tests.acceptance.test_user_stories.test_us03_complete_checkout`
- `tests.system.test_purchase_flow.test_full_purchase_registration_to_confirmation`

System فرآیند ثبت‌نام، جستجو، انتخاب محصول، افزودن به سبد، پرداخت Mock، تأیید، تاریخچه و خالی‌شدن سبد را بررسی می‌کند. US-01 شامل محصول فعال، قیمت تومان، RTL، نرمال‌سازی فارسی، نبود نتیجه و جستجوی خالی است. US-02 شامل تعداد ۲، جمع ۷۰۰۰۰۰ تومان، افزودن دوباره، رد موجودی ناکافی، تغییر و حذف است. US-03 شامل رد تلفن نامعتبر بدون سفارش و خرید موفق با snapshot و کاهش موجودی است. سایر حالات خطا، رقابت و idempotency در تست‌های قبلی مجدداً اجرا شده‌اند.

## وضعیت Selenium و علت جایگزینی

```text
NoSuchDriverException: Unable to obtain driver for chrome; For documentation on this error, please visit: https://www.selenium.dev/documentation/webdriver/troubleshooting/errors/driver_location
[2026-11-10T12:14:09Z ERROR selenium_manager::logger] error sending request for url (https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json)
    
    Caused by:
        0: client error (Connect)
        1: tunnel error: unsuccessful
```

در بررسی اولیه cache پیش‌فرض Selenium فقط‌خواندنی بود؛ مسیر قابل نوشتن برای اجرای suite تنظیم شده است. تشخیص بالا از تلاش واقعی suite با cache قابل نوشتن است. فقط شکست راه‌اندازی Selenium باعث fallback می‌شود؛ شکست assertion به Playwright تغییر مسیر نمی‌دهد. اگر هر دو مرورگر اجرا نشوند تست‌ها error می‌شوند، نه skip یا pass.

## تصاویر همین اجرا

- [stage-6-test_full_purchase_registration_to_confirmation.png](stage-6-test_full_purchase_registration_to_confirmation.png)
- [stage-6-test_us01_search_product.png](stage-6-test_us01_search_product.png)
- [stage-6-test_us02_add_to_cart.png](stage-6-test_us02_add_to_cart.png)
- [stage-6-test_us03_complete_checkout.png](stage-6-test_us03_complete_checkout.png)

گزارش HTML جزئیات همه تست‌ها را دارد؛ تصاویر و metadata این نوبت جداگانه ذخیره شده‌اند. زمان‌ها و نسخه‌ها داده واقعی اجرا هستند. این گزارش تأیید اتصال زرین‌پال یا استقرار تولید نیست.
