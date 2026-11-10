"""Execute all tests once and generate final Markdown/HTML from current evidence."""
from datetime import datetime
import html
import json
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'docs/test-reports'
STAGES = [
    ('۱', 'نیازمندی‌ها، داستان‌های کاربر، معماری، ER و اسکلت Flask/pytest.', 'تستی وجود نداشت؛ خروج اولیه pytest کد ۵ بود و قبولی محسوب نشد.'),
    ('۲', 'کارخانه برنامه، تنظیمات، SQLAlchemy، SQLite و قیود مدل‌ها.', '۲۳ تست مدل و کارخانه موفق؛ منبع: stage-2.xml.'),
    ('۳', 'ثبت‌نام و ورود scrypt، جستجو و فیلترها، صفحات RTL و ارتقای دیتابیس.', '۵۶ تست موفق: ۲۳ واحد و ۳۳ یکپارچه؛ منبع: stage-3.xml.'),
    ('۴', 'سبد، checkout اتمیک، پرداخت Mock، تأیید و تاریخچه با مالکیت.', '۸۳ تست موفق: ۲۳ واحد و ۶۰ یکپارچه؛ منبع: stage-4.xml.'),
    ('۵', 'پنل ادمین، مدیریت موجودی و سفارش، UI مینیمال، وزیرمتن و خطاهای فارسی.', '۱۱۵ تست موفق: ۲۳ واحد و ۹۲ یکپارچه؛ منبع: stage-5.xml.'),
    ('۶', 'یک فرآیند System و سه سناریوی پذیرش روی سایت زنده؛ Selenium و fallback به Playwright.', '۱۱۹ تست موفق: ۲۳ واحد، ۹۲ یکپارچه، ۱ سیستم، ۳ پذیرش؛ منبع: stage-6.xml.'),
    ('۷', 'README یکپارچه، اجرای دوباره کل suite و گزارش تجمیعی قابل بازتولید.', 'نتیجه این مرحله فقط از XML اجرای جدید در جدول زیر محاسبه می‌شود.'),
]
LIMITS = [
    'پرداخت فقط Mock است؛ زرین‌پال، callback و verify واقعی فعال نیستند. هیچ اطلاعات کارت دریافت یا ذخیره نمی‌شود.',
    'تماس درگاه واقعی نیازمند جریان pending/redirect/verify خارج از قفل SQLite و طراحی رزرو/انقضای موجودی است.',
    'لغو و بازپرداخت، ارسال واقعی، مالیات، تخفیف، آپلود تصویر و تنوع چندسایز/رنگ برای یک محصول وجود ندارند.',
    'تاریخچه مهمان به cookie همان سبد وابسته است؛ سفارش مهمان به حساب منتقل نمی‌شود.',
    'بازیابی رمز، تأیید ایمیل، محدودسازی تلاش ورود و ممیزی جامع امنیت پیاده‌سازی نشده‌اند.',
    'SQLite برای بار نوشتن بالا محدود است؛ جستجو در حافظه و بدون صفحه‌بندی برای کاتالوگ بزرگ نیازمند بازطراحی است.',
    'upgrade-db فقط ارتقاهای مشخص این پروژه را انجام می‌دهد؛ migration عمومی و قفل کامل وابستگی‌های گذرا وجود ندارند.',
    'repositories هنوز اسکلت است؛ بخشی از orchestration و ORM در routeهای سفارش قرار دارد.',
    'سرور توسعه و debug برای تولید مناسب نیستند؛ HTTPS، کلید پایدار، تنظیم cookie امن و استقرار WSGI جداگانه لازم‌اند.',
    'نتیجه Playwright به معنی موفقیت Selenium نیست؛ ابزار جایگزین و علت واقعی آن پایین ثبت شده‌اند.',
]


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    xml_path = REPORTS / 'stage-7.xml'
    html_path = REPORTS / 'stage-7.html'
    metadata = REPORTS / 'stage-6-browser.json'
    # The shared fixture uses stage-6 names. Preserve historical artifacts exactly.
    shared = [metadata, *REPORTS.glob('stage-6-test_*.png')]
    backup = {p: p.read_bytes() for p in shared if p.exists()}
    for p in (xml_path, html_path, REPORTS / 'stage-7-browser.json', *REPORTS.glob('stage-7-test_*.png')):
        p.unlink(missing_ok=True)
    for p in shared:
        p.unlink(missing_ok=True)
    started = datetime.now(ZoneInfo('Asia/Tehran')).isoformat()
    revision = git('rev-parse', 'HEAD')
    command = [sys.executable, '-m', 'pytest', 'tests', '--html=' + str(html_path), '--self-contained-html', '--junitxml=' + str(xml_path)]
    try:
        result = subprocess.run(command, cwd=ROOT, check=False)
        browser = json.loads(metadata.read_text()) if metadata.exists() else {'backend': 'not established', 'browser_version': 'unknown', 'fallback_reason': 'No browser metadata from this run.'}
        if metadata.exists():
            shutil.copyfile(metadata, REPORTS / 'stage-7-browser.json')
        for p in REPORTS.glob('stage-6-test_*.png'):
            shutil.copyfile(p, p.with_name(p.name.replace('stage-6-', 'stage-7-', 1)))
    finally:
        for p in [metadata, *REPORTS.glob('stage-6-test_*.png')]:
            if p in backup:
                p.write_bytes(backup[p])
            else:
                p.unlink(missing_ok=True)
    if not xml_path.exists():
        print('No current XML; final report not generated.', file=sys.stderr)
        return result.returncode or 1
    cases = list(ET.parse(xml_path).getroot().iter('testcase'))
    if not cases:
        print('Zero tests; final report not generated.', file=sys.stderr)
        return result.returncode or 1
    counts = {k: dict(passed=0, failed=0, error=0, skipped=0) for k in ('Unit', 'Integration', 'System', 'Acceptance', 'Other')}
    for case in cases:
        kind = next((k for k in counts if '.' + k.lower() + '.' in '.' + case.get('classname', '') + '.'), 'Other')
        outcome = 'error' if case.find('error') is not None else 'failed' if case.find('failure') is not None else 'skipped' if case.find('skipped') is not None else 'passed'
        counts[kind][outcome] += 1
    totals = {k: sum(c[k] for c in counts.values()) for k in ('passed', 'failed', 'error', 'skipped')}
    rows = [(k, *v.values(), sum(v.values())) for k, v in counts.items() if sum(v.values())]
    rows.append(('کل', *totals.values(), len(cases)))
    headers = ('نوع', 'Passed', 'Failed', 'Error', 'Skipped', 'مجموع')
    md_table = '| ' + ' | '.join(headers) + ' |\n|---|---:|---:|---:|---:|---:|\n' + '\n'.join('| ' + ' | '.join(map(str, row)) + ' |' for row in rows)
    commits = [line.split('\t', 1) for line in git('log', '--reverse', '--format=%h%x09%s').splitlines()]
    stage_md = '\n'.join(f'| {n} | {description} | {evidence} |' for n, description, evidence in STAGES)
    commit_md = '\n'.join(f'- `{sha}` — {title}' for sha, title in commits)
    limit_md = '\n'.join('- ' + text for text in LIMITS)
    reason = browser.get('fallback_reason') or 'Selenium started successfully; no fallback.'
    summary = f'''# گزارش نهایی تجمیعی فروشگاه پوشه

## معرفی و روش ساخت
فروشگاه آنلاین لباس ایرانی با Flask، SQLAlchemy و SQLite، رابط فارسی RTL، وزیرمتن محلی و قیمت صحیح تومان. کدنویسی، مستندسازی، طراحی، تست و آماده‌سازی کامیت‌ها در هفت مرحله توسط عامل AI و بدون ویرایش دستی کد انجام شد؛ انسان درخواست مراحل و ادغام PRها را انجام داده است. ادعای نتیجه تست تنها به شواهد اجرای واقعی محدود است.

## خلاصه مراحل
| مرحله | خروجی | شواهد تاریخی |
|---|---|---|
{stage_md}

منابع تاریخی در [test-reports](test-reports/) نگهداری می‌شوند؛ این اعداد به اجرای فعلی نسبت داده نشده‌اند.

## اجرای نهایی مرحله ۷
- شروع (Asia/Tehran): {started}
- نسخه پایه هنگام اجرا: `{revision}`؛ فایل‌های مستندات و گزارش‌ساز مرحله ۷ در working tree بودند.
- فرمان بازتولید: `python scripts/run_final_report.py`
- کد خروج واقعی pytest: **{result.returncode}**
- مرورگر: **{browser['backend']} headless / Chromium {browser['browser_version']}**

{md_table}

[خروجی کامل HTML pytest](test-reports/stage-7.html) · [JUnit XML اجرای تازه](test-reports/stage-7.xml) · [metadata مرورگر](test-reports/stage-7-browser.json)

Unit شامل مدل‌ها، قیود، کارخانه و ماندگاری دیتابیس است. Integration شامل احراز هویت، کاتالوگ، سبد، پرداخت، rollback، خرید هم‌زمان و مجوز ادمین است. System فرآیند حساب‌دار ثبت‌نام تا جستجو، سبد، پرداخت Mock، تأیید، تاریخچه و سبد خالی را اجرا می‌کند. Acceptance شامل US-01 جستجو، US-02 افزودن/تغییر/حذف و US-03 تکمیل خرید با حالت خطا است.

تست‌های System و Acceptance روی سرور HTTP واقعی، پورت آزاد و فایل SQLite مستقل اجرا می‌شوند؛ فرم‌ها توسط مرورگر و CSRF واقعی ارسال می‌شوند. تغییر موجودی، snapshot سفارش و مبلغ در دیتابیس نیز بررسی می‌شوند. داده شخصی آزمون ساختگی است و هیچ اطلاعات کارت دریافت یا ذخیره نمی‌شود. پرداخت شبکه بانکی تست نشده است.

## Selenium و Playwright
در بررسی مرحله ۶ cache پیش‌فرض فقط‌خواندنی بود؛ مسیر موقت قابل نوشتن تنظیم شد. علت واقعی انتخاب backend در اجرای نهایی:
```text
{reason.strip()}
```
فقط شکست startup Selenium باعث fallback می‌شود؛ assertion شکست‌خورده تغییر backend نمی‌دهد. اگر هر دو اجرا نشوند، error ثبت می‌شود، نه skip یا نتیجه ساختگی. نسخه‌ها و شمارش‌ها از metadata و XML همین اجرا استخراج شده‌اند.

## معماری و راه‌اندازی
کارخانه Flask، blueprintهای فروشگاه/سفارش/ادمین، شش مدل رابطه‌ای و مرز PaymentGateway، همراه با checkout تراکنشی SQLite استفاده می‌شوند. برای نصب، کلید نشست، upgrade-db، ثبت حساب و اعطای نقش CLI، [README](../README.md) را ببینید. تصاویر محصول محلی‌اند و وزیرمتن با مجوز OFL در مخزن قرار دارد.

## کامیت‌ها
تاریخچه زیر هنگام تولید گزارش از Git خوانده شد؛ شامل کامیت‌های اولیه و mergeهای مراحل ۱ تا ۶ است. کامیت حاوی همین گزارش و شاخه مرحله ۷ پس از تولید به تاریخچه اضافه می‌شود و عمداً به عنوان کامیت از پیش موجود درج نشده است.

{commit_md}

## محدودیت‌های شناخته‌شده
{limit_md}

## شواهد و بازتولید
گزارش HTML تجمیعی [اینجاست](final-report.html). XML و metadata نهایی در test-reports ثبت شده‌اند؛ تصاویر `stage-7-test_*.png` نیز متعلق به همین اجرا هستند. گزارش‌ساز فایل‌های تاریخی مرحله ۶ را پس از اجرای fixture حفظ می‌کند و کد خروج pytest را برمی‌گرداند. قبولی آزمون‌ها فقط قابلیت‌های بررسی‌شده را اثبات می‌کند؛ انتشار محیط یا استقرار تولید انجام نشده است.
'''
    (ROOT / 'docs/final-report.md').write_text(summary, encoding='utf-8')
    esc = html.escape
    table = '<table><thead><tr>' + ''.join('<th>' + esc(h) + '</th>' for h in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + esc(str(c)) + '</td>' for c in row) + '</tr>' for row in rows) + '</tbody></table>'
    sections = ''.join('<article><h3>مرحله ' + esc(n) + '</h3><p>' + esc(d) + '</p><p>' + esc(e) + '</p></article>' for n, d, e in STAGES)
    document = '''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>گزارش نهایی پوشه</title><style>@font-face{font-family:Vazirmatn;src:url('../app/static/fonts/Vazirmatn.woff2')}body{font-family:Vazirmatn,Tahoma,sans-serif;background:#faf9f6;color:#243c35;line-height:1.9;max-width:1100px;margin:auto;padding:2rem}table{border-collapse:collapse;width:100%;background:white}th,td{border:1px solid #ccd4ca;padding:.7rem;text-align:right}article{background:white;border:1px solid #dce2d8;border-radius:10px;padding:1rem;margin:1rem 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#edf1e9;padding:1rem}a{color:#164b40}code{direction:ltr;unicode-bidi:isolate}h1,h2{color:#164b40}.table-wrap{overflow:auto}</style></head><body>'''
    document += '<h1>گزارش نهایی تجمیعی پوشه</h1><p>ساخته‌شده توسط AI؛ نتیجه آزمون‌ها از اجرای واقعی همین نوبت.</p><h2>نتیجه اجرای نهایی</h2><p>' + esc(started) + ' — pytest exit ' + str(result.returncode) + '</p><div class="table-wrap">' + table + '</div>'
    document += '<p><a href="test-reports/stage-7.html">جزئیات pytest</a> · <a href="test-reports/stage-7.xml">JUnit XML</a> · <a href="../README.md">README</a> · <a href="final-report.md">نسخه Markdown</a></p><h2>خلاصه مراحل</h2>' + sections
    document += '<h2>متن کامل گزارش و شواهد</h2><pre>' + esc(summary) + '</pre></body></html>'
    (ROOT / 'docs/final-report.html').write_text(document, encoding='utf-8')
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
