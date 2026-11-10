# فروشگاه آنلاین لباس ایرانی

فروشگاه فارسی، راست‌به‌چپ و با قیمت صحیح به **تومان**؛ فناوری هدف Flask و SQLite با آزمون‌های pytest و Selenium.

## وضعیت مرحله ۱
این مرحله شامل مستندات، اسکلت پوشه‌ها و ابزارهای توسعه است. مدل‌ها، کارخانه برنامه، مسیرهای HTTP، رابط و منطق خرید هنوز پیاده‌سازی نشده‌اند؛ سرور قابل اجرا و تست کاربردی در این مرحله وجود ندارد.

## پیش‌نیازها و نصب
Python 3.12 و Git لازم‌اند. SQLite همراه Python است و سرویس مستقل لازم ندارد.

```bash
git clone https://github.com/minooaslani137853-boop/iranian-clothing-shop.git
cd iranian-clothing-shop
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

در PowerShell فعال‌سازی با `.venv\Scripts\Activate.ps1` است. نسخه وابستگی‌های مستقیم ثابت است؛ requirements فایل قفل وابستگی‌های گذرا نیست.

## اجرا در مرحله بعد
پس از پیاده‌سازی `create_app` دستور زیر قابل استفاده خواهد بود؛ در مرحله ۱ کار نمی‌کند:

```bash
flask --app app:create_app run --debug
```

پایگاه داده محلی در `instance/shop.sqlite3` نگهداری خواهد شد. کلید `SECRET_KEY` در تولید از محیط دریافت شود؛ داده مشتری و رمز در Git ثبت نشوند. debug فقط برای توسعه است.

## ساختار
```text
app/
  __init__.py
  routes/
  services/
  repositories/
  templates/
  static/{css,js,images}/
tests/{unit,integration,system,acceptance}/
docs/
  requirements.md
  user-stories.md
  architecture.md
  er-diagram.md
  test-reports/
```

## آزمون و گزارش
```bash
python -m pytest tests/unit tests/integration
python -m pytest tests/system tests/acceptance
python -m pytest --html=docs/test-reports/pytest-report.html --self-contained-html
```

فعلاً پوشه‌های تست خالی‌اند؛ خروج با کد ۵ یعنی بدون آزمون، نه قبولی. پس از افزودن آزمون‌ها، HTML و تصاویر خطای Selenium در `docs/test-reports/` ذخیره شوند؛ خروجی تولیدشده در Git ثبت نمی‌شود.

Selenium به Chrome/Chromium و درایور سازگار نیاز دارد. Selenium Manager در صورت دسترسی شبکه می‌تواند درایور را دریافت کند. برای محیط بدون نمایشگر از `--headless=new` و `--disable-dev-shm-usage` استفاده شود؛ fixture باید مرورگر را با `quit()` ببندد. تست‌ها باید از SQLite موقت و مستقل از داده واقعی استفاده کنند.

## مستندات و ادامه کار
[نیازمندی‌ها](docs/requirements.md)، [داستان‌های کاربر](docs/user-stories.md)، [معماری](docs/architecture.md)، [نمودار ER](docs/er-diagram.md).

مرحله بعد: کارخانه برنامه، schema و داده نمونه، جستجو، سبد، checkout و آزمون‌های واقعی. درگاه بانکی واقعی، مدیریت فروشگاه و استقرار تولید خارج از مرحله ۱ هستند.
