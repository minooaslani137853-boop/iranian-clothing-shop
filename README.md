# فروشگاه آنلاین لباس ایرانی

فروشگاه فارسی، راست‌به‌چپ و با قیمت صحیح به **تومان**؛ فناوری هدف Flask و SQLite با آزمون‌های pytest و Selenium.

## وضعیت مرحله ۲
Application Factory، تنظیمات، مدل‌های SQLAlchemy و SQLite پیاده‌سازی شده‌اند. مسیرهای فروشگاه، رابط و سرویس checkout هنوز پیاده‌سازی نشده‌اند؛ درخواست صفحه اصلی فعلاً 404 می‌دهد.

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

## اجرا و دیتابیس
```bash
source .venv/bin/activate
flask --app app:create_app init-db
flask --app app:create_app run --debug
```

`init-db` جدول‌های مفقود را می‌سازد و داده موجود را پاک نمی‌کند؛ جایگزین migration برای تغییر schema نیست. داده محلی در `instance/shop.sqlite3` است. SQLite foreign keys برای هر اتصال فعال می‌شود. کلید `SECRET_KEY` در تولید از محیط خوانده می‌شود؛ تا تنظیم آن قابلیت نشست قابل استفاده نیست. debug فقط برای توسعه است.

`create_app` یک dict تنظیمات یا کلاس تنظیمات می‌پذیرد؛ `TestingConfig` دیتابیس مستقل در حافظه و کلید مخصوص تست دارد. نمونه تغییر مسیر: `create_app({'SQLALCHEMY_DATABASE_URI': 'sqlite:////tmp/shop.sqlite3'})`.

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

۲۳ تست مدل و کارخانه در `tests/unit/` موجود است. پوشه‌های integration، system و acceptance هنوز خالی‌اند؛ اجرای آن‌ها به تنهایی کد ۵ می‌دهد. تست‌ها schema واقعی SQLite را در حافظه یا فایل موقت بررسی می‌کنند. گزارش مرحله ۲ در `docs/test-reports/stage-2.xml` و خلاصه در همان پوشه ثبت شده است؛ HTML تولیدشده به صورت محلی نگهداری می‌شود.

Selenium به Chrome/Chromium و درایور سازگار نیاز دارد. Selenium Manager در صورت دسترسی شبکه می‌تواند درایور را دریافت کند. برای محیط بدون نمایشگر از `--headless=new` و `--disable-dev-shm-usage` استفاده شود؛ fixture باید مرورگر را با `quit()` ببندد. تست‌ها باید از SQLite موقت و مستقل از داده واقعی استفاده کنند.

## مستندات و ادامه کار
[نیازمندی‌ها](docs/requirements.md)، [داستان‌های کاربر](docs/user-stories.md)، [معماری](docs/architecture.md)، [نمودار ER](docs/er-diagram.md).

مرحله بعد: داده نمونه، مسیرها، جستجو، سبد، سرویس checkout و آزمون‌های کاربردی. درگاه بانکی واقعی، مدیریت فروشگاه و استقرار تولید خارج از مرحله ۱ هستند.
