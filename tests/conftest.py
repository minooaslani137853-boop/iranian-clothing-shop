import pytest
from app import create_app
from app.config import TestingConfig
from app.extensions import db


@pytest.fixture
def app(tmp_path):
    application = create_app(TestingConfig)
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def live_shop(tmp_path):
    """Serve real HTTP on an OS-selected port, with a fresh file database per test."""
    from threading import Thread
    from urllib.request import urlopen
    from werkzeug.serving import make_server
    from app.models import Product
    application = create_app({
        'TESTING': True, 'SECRET_KEY': 'browser-test-only',
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{tmp_path / "browser.sqlite3"}',
    })
    with application.app_context():
        db.create_all()
        db.session.add_all([
            Product(name='مانتو ایرانی', description='پنبه خنک', price_toman=350000, stock=3, category='مانتو', size='M', color='آبی'),
            Product(name='پیراهن', price_toman=500000, stock=2),
            Product(name='مانتو پنهان', price_toman=300000, stock=1, is_active=False),
        ])
        db.session.commit()
    server = make_server('127.0.0.1', 0, application, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(base_url + '/products', timeout=10) as response:
            assert response.status == 200 and 'مانتو ایرانی' in response.read().decode()
        yield application, base_url
    finally:
        server.shutdown()
        thread.join(timeout=10)
        server.server_close()
        with application.app_context():
            db.session.remove()
            db.engine.dispose()


@pytest.fixture(scope='session')
def browser_engine(tmp_path_factory):
    """Try Selenium once; only startup failure selects real Playwright Chromium."""
    import json
    import os
    import shutil
    import subprocess
    from pathlib import Path
    from selenium import webdriver
    from selenium.common.exceptions import WebDriverException
    reports = Path('docs/test-reports')
    reports.mkdir(parents=True, exist_ok=True)
    # Never reuse a previous run's backend metadata after an early startup failure.
    metadata_path = reports / 'stage-6-browser.json'
    metadata_path.unlink(missing_ok=True)
    os.environ.setdefault('SE_CACHE_PATH', str(tmp_path_factory.mktemp('selenium-cache')))
    binary = os.environ.get('CHROME_BINARY') or shutil.which('chromium') or shutil.which('google-chrome')
    options = webdriver.ChromeOptions()
    if binary:
        options.binary_location = binary
    for argument in ('--headless=new', '--disable-dev-shm-usage', '--no-sandbox', '--window-size=1280,900'):
        options.add_argument(argument)
    fallback_reason = None
    try:
        probe = webdriver.Chrome(options=options)
    except WebDriverException as exc:
        fallback_reason = f'{type(exc).__name__}: {exc.msg}'
        # Capture the underlying Manager diagnosis without printing environment values.
        manager = Path(webdriver.__file__).parent / 'common/linux/selenium-manager'
        if manager.exists():
            try:
                diagnostic = subprocess.run([str(manager), '--browser', 'chrome', '--browser-path', binary or 'chromium', '--cache-path', os.environ['SE_CACHE_PATH'], '--debug'], capture_output=True, text=True, timeout=30)
                fallback_reason += '\n' + diagnostic.stdout + diagnostic.stderr
            except subprocess.TimeoutExpired:
                fallback_reason += '\nSelenium Manager diagnostic timed out after 30 seconds.'
    else:
        version = probe.capabilities['browserVersion']
        probe.quit()
        metadata_path.write_text(json.dumps({'backend': 'Selenium', 'browser_version': version, 'fallback_reason': None}, ensure_ascii=False, indent=2))
        yield 'selenium', options
        return
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        settings = {'headless': True, 'args': ['--no-sandbox', '--disable-dev-shm-usage']}
        if binary:
            settings['executable_path'] = binary
        engine = playwright.chromium.launch(**settings)
        metadata_path.write_text(json.dumps({'backend': 'Playwright', 'browser_version': engine.version, 'fallback_reason': fallback_reason}, ensure_ascii=False, indent=2))
        try:
            yield 'playwright', engine
        finally:
            engine.close()


@pytest.fixture
def browser(browser_engine, request):
    from pathlib import Path
    from tests.browser_support import PlaywrightBrowser, SeleniumBrowser
    backend, engine = browser_engine
    if backend == 'selenium':
        from selenium import webdriver
        instance = SeleniumBrowser(webdriver.Chrome(options=engine))
    else:
        instance = PlaywrightBrowser(engine.new_context(viewport={'width': 1280, 'height': 900}, locale='fa-IR'))
    request.node.user_properties.append(('browser_backend', backend))
    try:
        yield instance
    finally:
        try:
            instance.screenshot(Path('docs/test-reports') / ('stage-6-' + request.node.name + '.png'))
        finally:
            instance.close()
