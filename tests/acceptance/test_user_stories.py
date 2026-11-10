import pytest

from app.extensions import db
from app.models import CartItem, CustomerOrder, Product
from tests.browser_support import add_to_cart, complete_checkout

pytestmark = pytest.mark.acceptance


def test_us01_search_product(browser, live_shop):
    _, url = live_shop
    browser.visit(url + '/products')
    assert browser.rtl()
    browser.fill('#q', 'مانتو')
    browser.click('.filters button')
    assert 'مانتو ایرانی' in browser.text('.product-grid')
    assert 'پیراهن' not in browser.text('.product-grid')
    assert 'مانتو پنهان' not in browser.text('.product-grid')
    assert '350,000 تومان' in browser.text('.product-grid')
    browser.fill('#q', 'ايراني')
    browser.click('.filters button')
    assert 'مانتو ایرانی' in browser.text('.product-grid')
    browser.fill('#q', 'کالای ناموجود')
    browser.click('.filters button')
    assert 'محصولی یافت نشد' in browser.text()
    browser.fill('#q', '')
    browser.click('.filters button')
    assert 'مانتو ایرانی' in browser.text('.product-grid') and 'پیراهن' in browser.text('.product-grid')


def test_us02_add_to_cart(browser, live_shop):
    application, url = live_shop
    add_to_cart(browser, url)
    assert '700,000 تومان' in browser.text()
    with application.app_context():
        assert db.session.query(CartItem).one().quantity == 2
        assert db.session.get(Product, 1).stock == 3
    add_to_cart(browser, url, '1')
    assert '1,050,000 تومان' in browser.text()
    browser.fill('#quantity-1', '4')
    browser.click('.quantity-form button')
    assert 'موجودی کافی نیست' in browser.text()
    with application.app_context():
        assert db.session.query(CartItem).one().quantity == 3
    browser.visit(url + '/cart')
    browser.fill('#quantity-1', '1')
    browser.click('.quantity-form button')
    browser.wait_path('/cart')
    assert '350,000 تومان' in browser.text()
    browser.click('main .button-danger')
    browser.wait_path('/cart')
    assert 'سبد خرید خالی است' in browser.text()
    with application.app_context():
        assert db.session.query(CartItem).count() == 0


def test_us03_complete_checkout(browser, live_shop):
    application, url = live_shop
    add_to_cart(browser, url)
    browser.visit(url + '/checkout')
    browser.fill('#recipient_name', 'گیرنده آزمایشی')
    browser.fill('#phone', '123')
    browser.fill('#address', 'نشانی ساختگی آزمون')
    browser.click('main form button')
    assert 'نام، نشانی و تلفن همراه معتبر' in browser.text()
    with application.app_context():
        assert db.session.query(CustomerOrder).count() == 0
        assert db.session.get(Product, 1).stock == 3
    complete_checkout(browser, url)
    with application.app_context():
        purchase = db.session.query(CustomerOrder).one()
        assert purchase.user_id is None and purchase.total_toman == 700000
        assert purchase.phone == '09123456789'
        assert db.session.get(Product, 1).stock == 1
        assert db.session.query(CartItem).count() == 0
        assert purchase.tracking_code in browser.text()
