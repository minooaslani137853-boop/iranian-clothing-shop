"""Run the real suite and derive both reports from this run's JUnit XML only."""
import html
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'docs/test-reports'


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    xml_path = REPORTS / 'stage-6.xml'
    html_path = REPORTS / 'stage-6.html'
    md_path = REPORTS / 'stage-6-summary.md'
    metadata_path = REPORTS / 'stage-6-browser.json'
    for path in [xml_path, html_path, md_path, metadata_path, *REPORTS.glob('stage-6-test_*.png')]:
        path.unlink(missing_ok=True)
    started = datetime.now(ZoneInfo('Asia/Tehran')).isoformat()
    command = [sys.executable, '-m', 'pytest', 'tests', '--html=' + str(html_path), '--self-contained-html', '--junitxml=' + str(xml_path)]
    result = subprocess.run(command, cwd=ROOT, check=False)
    if not xml_path.exists():
        print('No current-run XML exists; no result report was invented.', file=sys.stderr)
        return result.returncode or 1
    cases = list(ET.parse(xml_path).getroot().iter('testcase'))
    if not cases:
        print('Zero tests executed; readiness is not established.', file=sys.stderr)
        return result.returncode or 1
    categories = {name: {'passed': 0, 'failed': 0, 'error': 0, 'skipped': 0} for name in ('Unit', 'Integration', 'System', 'Acceptance', 'Other')}
    for case in cases:
        category = next((name for name in categories if '.' + name.lower() + '.' in '.' + case.get('classname', '') + '.'), 'Other')
        outcome = 'error' if case.find('error') is not None else 'failed' if case.find('failure') is not None else 'skipped' if case.find('skipped') is not None else 'passed'
        categories[category][outcome] += 1
    backend = json.loads(metadata_path.read_text()) if metadata_path.exists() else {'backend': 'Not established', 'browser_version': 'unknown', 'fallback_reason': 'No current-run browser metadata was produced.'}
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    rows = ['| نوع | Passed | Failed | Error | Skipped | مجموع |', '|---|---:|---:|---:|---:|---:|']
    for name, outcomes in categories.items():
        if sum(outcomes.values()):
            rows.append(f"| {name} | {outcomes['passed']} | {outcomes['failed']} | {outcomes['error']} | {outcomes['skipped']} | {sum(outcomes.values())} |")
    total = {key: sum(counts[key] for counts in categories.values()) for key in ('passed', 'failed', 'error', 'skipped')}
    rows.append(f"| **کل** | {total['passed']} | {total['failed']} | {total['error']} | {total['skipped']} | {len(cases)} |")
    browser_cases = [case for case in cases if any('.' + kind + '.' in '.' + case.get('classname', '') + '.' for kind in ('system', 'acceptance'))]
    browser_rows = '\n'.join('- `' + case.get('classname', '') + '.' + case.get('name', '') + '`' for case in browser_cases)
    screenshots = sorted(REPORTS.glob('stage-6-test_*.png'))
    image_links = '\n'.join(f'- [{path.name}]({path.name})' for path in screenshots)
    reason = backend.get('fallback_reason') or 'Selenium started successfully; no fallback used.'
    summary = f'''# گزارش نهایی مرحله ۶

این گزارش از XML اجرای واقعی همین نوبت تولید شده است؛ شمارش‌ها دستی نیستند.

- شروع اجرا (Asia/Tehran): {started}
- نسخه کد هنگام اجرا: `{revision}` (تغییرات مرحله ۶ در working tree)
- فرمان قابل تکرار: `python scripts/run_test_reports.py`
- کد خروج pytest: **{result.returncode}**
- مرورگر واقعی: **{backend['backend']} headless / Chromium {backend['browser_version']}**
- منبع جزئیات: [JUnit XML](stage-6.xml) و [گزارش HTML](stage-6.html).

## نتیجه همه انواع تست

{chr(10).join(rows)}

## اجرای مرورگر

هر تست سرور واقعی Werkzeug روی پورت آزاد loopback و دیتابیس فایل SQLite مستقل دارد. ابتدا پاسخ HTTP محصولات بررسی می‌شود؛ فرم‌ها از طریق مرورگر و CSRF واقعی ارسال می‌شوند. هیچ درخواست خرید با Flask test client در تست‌های System و Acceptance انجام نمی‌شود. در پایان سرور، اتصال دیتابیس، context و مرورگر بسته می‌شوند. داده‌های نام، ایمیل، تلفن و نشانی ساختگی‌اند و هیچ اطلاعات کارت دریافت یا ذخیره نمی‌شود. پرداخت واقعی بانکی اجرا نشده؛ پرداخت Mock واقعی برنامه اجرا شده است.

{browser_rows}

System فرآیند ثبت‌نام، جستجو، انتخاب محصول، افزودن به سبد، پرداخت Mock، تأیید، تاریخچه و خالی‌شدن سبد را بررسی می‌کند. US-01 شامل محصول فعال، قیمت تومان، RTL، نرمال‌سازی فارسی، نبود نتیجه و جستجوی خالی است. US-02 شامل تعداد ۲، جمع ۷۰۰۰۰۰ تومان، افزودن دوباره، رد موجودی ناکافی، تغییر و حذف است. US-03 شامل رد تلفن نامعتبر بدون سفارش و خرید موفق با snapshot و کاهش موجودی است. سایر حالات خطا، رقابت و idempotency در تست‌های قبلی مجدداً اجرا شده‌اند.

## وضعیت Selenium و علت جایگزینی

```text
{reason.strip()}
```

در بررسی اولیه cache پیش‌فرض Selenium فقط‌خواندنی بود؛ مسیر قابل نوشتن برای اجرای suite تنظیم شده است. تشخیص بالا از تلاش واقعی suite با cache قابل نوشتن است. فقط شکست راه‌اندازی Selenium باعث fallback می‌شود؛ شکست assertion به Playwright تغییر مسیر نمی‌دهد. اگر هر دو مرورگر اجرا نشوند تست‌ها error می‌شوند، نه skip یا pass.

## تصاویر همین اجرا

{image_links or 'تصویری در این اجرا تولید نشد.'}

گزارش HTML جزئیات همه تست‌ها را دارد؛ تصاویر و metadata این نوبت جداگانه ذخیره شده‌اند. زمان‌ها و نسخه‌ها داده واقعی اجرا هستند. این گزارش تأیید اتصال زرین‌پال یا استقرار تولید نیست.
'''
    md_path.write_text(summary, encoding='utf-8')
    if html_path.exists():
        appendix = '<section dir="rtl" lang="fa"><h2>گزارش نهایی همه انواع تست</h2><pre style="white-space:pre-wrap">' + html.escape(summary) + '</pre></section>'
        document = html_path.read_text(encoding='utf-8')
        html_path.write_text(document.replace('</body>', appendix + '</body>'), encoding='utf-8')
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
