import pytest

from app.extensions import db
from app.models import CartItem, CustomerOrder, Product, User
from tests.browser_support import complete_checkout

pytestmark = pytest.mark.system


def test_full_purchase_registration_to_confirmation(browser, live_shop):
    application, url = live_shop
    browser.visit(url + '/register')
    browser.fill('#email', 'system-buyer@example.com')
    browser.fill('#password', 'system-test-password')
    browser.click('main form button')
    browser.wait_path('/products')
    assert 'system-buyer@example.com' in browser.text('header')
    browser.fill('#q', 'مانتو')
    browser.click('.filters button')
    assert 'مانتو ایرانی' in browser.text('.product-grid')
    assert 'مانتو پنهان' not in browser.text('.product-grid')
    browser.click('.product-info h3 a')
    browser.wait_path('/products/1')
    browser.fill('#quantity', '2')
    browser.click('main form button')
    browser.wait_path('/cart')
    assert '700,000 تومان' in browser.text()
    complete_checkout(browser, url)
    with application.app_context():
        purchase = db.session.query(CustomerOrder).one()
        assert purchase.user_id == db.session.query(User).one().id
        assert purchase.total_toman == 700000 and purchase.status == 'mock_paid'
        assert purchase.items[0].quantity == 2
        assert purchase.payment_reference.startswith('MOCK-')
        assert db.session.get(Product, 1).stock == 1
        assert db.session.query(CartItem).count() == 0
        tracking = purchase.tracking_code
    browser.visit(url + '/orders')
    assert tracking in browser.text()
    browser.visit(url + '/cart')
    assert 'سبد خرید خالی است' in browser.text()
