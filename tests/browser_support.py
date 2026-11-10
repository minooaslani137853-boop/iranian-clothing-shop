"""Real browser adapters; fallback applies only to browser startup failures."""
from urllib.parse import urlsplit


class SeleniumBrowser:
    def __init__(self, driver):
        self.driver = driver

    def visit(self, url):
        self.driver.get(url)

    def fill(self, selector, value):
        from selenium.webdriver.common.by import By
        field = self.driver.find_element(By.CSS_SELECTOR, selector)
        field.clear()
        field.send_keys(value)

    def click(self, selector):
        from selenium.webdriver.common.by import By
        self.driver.find_element(By.CSS_SELECTOR, selector).click()

    def text(self, selector='main'):
        from selenium.webdriver.common.by import By
        return self.driver.find_element(By.CSS_SELECTOR, selector).text

    def wait_path(self, path, prefix=False):
        from selenium.webdriver.support.ui import WebDriverWait
        WebDriverWait(self.driver, 10).until(lambda d: urlsplit(d.current_url).path.startswith(path) if prefix else urlsplit(d.current_url).path == path)

    def screenshot(self, path):
        self.driver.save_screenshot(str(path))

    def rtl(self):
        return self.driver.execute_script('return document.documentElement.dir') == 'rtl'

    def close(self):
        self.driver.quit()


class PlaywrightBrowser:
    def __init__(self, context):
        self.context = context
        self.page = context.new_page()
        self.page.set_default_timeout(10000)

    def visit(self, url):
        self.page.goto(url, wait_until='networkidle')

    def fill(self, selector, value):
        self.page.locator(selector).fill(value)

    def click(self, selector):
        self.page.locator(selector).click()

    def text(self, selector='main'):
        return self.page.locator(selector).inner_text()

    def wait_path(self, path, prefix=False):
        self.page.wait_for_url(lambda url: urlsplit(url).path.startswith(path) if prefix else urlsplit(url).path == path)

    def screenshot(self, path):
        self.page.screenshot(path=str(path), full_page=True)

    def rtl(self):
        return self.page.locator('html').get_attribute('dir') == 'rtl'

    def close(self):
        self.context.close()


def add_to_cart(browser, base_url, quantity='2'):
    browser.visit(base_url + '/products/1')
    browser.fill('#quantity', quantity)
    browser.click('main form button')
    browser.wait_path('/cart')


def complete_checkout(browser, base_url):
    browser.visit(base_url + '/checkout')
    assert '700,000 تومان' in browser.text()
    assert 'هیچ اطلاعات کارت' in browser.text()
    browser.fill('#recipient_name', 'گیرنده آزمایشی')
    browser.fill('#phone', '۰۹۱۲۳۴۵۶۷۸۹')
    browser.fill('#address', 'نشانی ساختگی آزمون')
    browser.click('main form button')
    browser.wait_path('/orders/', prefix=True)
    assert 'سفارش ثبت شد' in browser.text()
    assert 'پرداخت آزمایشی موفق (Mock)' in browser.text()
    assert '700,000 تومان' in browser.text()
