import pytest
from sqlalchemy import event

from app.extensions import db
from app.models import CartItem, CustomerOrder, Product, User
from app.services.payments import PaymentError, PaymentReceipt

pytestmark = pytest.mark.integration


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def product(app):
    p = Product(name='مانتو', price_toman=350000, stock=3)
    db.session.add(p)
    db.session.commit()
    return p


def post(client, path, data=None):
    client.get('/products')
    with client.session_transaction() as s:
        token = s['csrf_token']
    return client.post(path, data={**(data or {}), 'csrf_token': token})


def add(client, product, quantity='2'):
    return post(client, '/cart/items', {'product_id': product.id, 'quantity': quantity})


def prepare(client, product):
    assert add(client, product).status_code == 302
    assert client.get('/checkout').status_code == 200
    with client.session_transaction() as s:
        return s['checkout']['key']


def checkout(client, key, **overrides):
    return post(client, '/checkout', {'checkout_key': key, 'recipient_name': 'نام آزمایشی', 'phone': '۰۹۱۲۳۴۵۶۷۸۹', 'address': 'نشانی آزمایشی', **overrides})


def test_cart_add_update_delete_total(client, product):
    assert add(client, product).status_code == 302
    assert '700,000 تومان' in client.get('/cart').get_data(as_text=True)
    assert product.stock == 3
    assert add(client, product, '1').status_code == 302
    assert db.session.query(CartItem).one().quantity == 3
    assert post(client, f'/cart/items/{product.id}/update', {'quantity': '1'}).status_code == 302
    assert '350,000 تومان' in client.get('/cart').get_data(as_text=True)
    assert post(client, f'/cart/items/{product.id}/delete').status_code == 302
    assert db.session.query(CartItem).count() == 0
    assert 'سبد خرید خالی است' in client.get('/cart').get_data(as_text=True)


@pytest.mark.parametrize('quantity', ['0', '-1', '1.5', '4', 'x', str(2**65)])
def test_invalid_add_no_mutation(client, product, quantity):
    assert add(client, product, quantity).status_code == 400
    assert db.session.query(CartItem).count() == 0
    assert product.stock == 3


def test_overstock_update_and_inactive(client, product):
    add(client, product)
    assert add(client, product, '2').status_code == 400
    assert post(client, f'/cart/items/{product.id}/update', {'quantity': '4'}).status_code == 400
    assert db.session.query(CartItem).one().quantity == 2
    product.is_active = False
    db.session.commit()
    assert add(client, product, '1').status_code == 400


def test_cart_isolation_and_csrf(client, app, product):
    add(client, product)
    other = app.test_client()
    assert 'سبد خرید خالی است' in other.get('/cart').get_data(as_text=True)
    assert post(other, f'/cart/items/{product.id}/delete').status_code == 404
    assert post(other, f'/cart/items/{product.id}/update', {'quantity': '1'}).status_code == 404
    for path in ['/cart/items', f'/cart/items/{product.id}/delete', f'/cart/items/{product.id}/update', '/checkout']:
        assert client.post(path).status_code == 400
    assert db.session.query(CartItem).count() == 1


def test_success_repeat_snapshot_and_guest_access(client, app, product):
    key = prepare(client, product)
    response = checkout(client, key, total_toman='1', card_number='SHOULD-NOT-BE-STORED')
    assert response.status_code == 302
    purchase = db.session.query(CustomerOrder).one()
    assert purchase.total_toman == 700000
    assert purchase.status == 'mock_paid' and purchase.payment_reference.startswith('MOCK-')
    assert purchase.phone == '09123456789'
    assert product.stock == 1
    assert db.session.query(CartItem).count() == 0
    assert 'سفارش ثبت شد' in client.get(response.location).get_data(as_text=True)
    assert purchase.tracking_code in client.get('/orders').get_data(as_text=True)
    assert checkout(client, key).location == response.location
    assert db.session.query(CustomerOrder).count() == 1 and product.stock == 1
    product.name, product.price_toman = 'نام جدید', 900000
    db.session.commit()
    html = client.get(response.location).get_data(as_text=True)
    assert '700,000 تومان' in html and 'نام جدید' not in html
    assert 'SHOULD-NOT-BE-STORED' not in str(purchase.__dict__)
    assert app.test_client().get(response.location).status_code == 404
    assert purchase.tracking_code not in app.test_client().get('/orders').get_data(as_text=True)


@pytest.mark.parametrize('overrides', [{'phone': '123'}, {'recipient_name': ''}, {'address': ''}, {'recipient_name': 'x' * 101}, {'address': 'x' * 1001}])
def test_checkout_invalid_fields(client, product, overrides):
    key = prepare(client, product)
    assert checkout(client, key, **overrides).status_code == 400
    assert db.session.query(CustomerOrder).count() == 0
    assert db.session.query(CartItem).one().quantity == 2 and product.stock == 3


@pytest.mark.parametrize('change', ['stock', 'price', 'inactive', 'cart'])
def test_checkout_rechecks_current_state(client, product, change):
    key = prepare(client, product)
    if change == 'stock':
        product.stock = 1
    elif change == 'price':
        product.price_toman = 400000
    elif change == 'inactive':
        product.is_active = False
    else:
        db.session.query(CartItem).one().quantity = 1
    db.session.commit()
    assert checkout(client, key).status_code == 409
    assert db.session.query(CustomerOrder).count() == 0
    assert db.session.query(CartItem).count() == 1


def test_empty_and_unconfirmed_checkout(client):
    assert client.get('/checkout').status_code == 400
    assert checkout(client, 'invented').status_code == 409


@pytest.mark.parametrize('mode', ['exception', 'amount'])
def test_payment_failure_rolls_back(client, app, product, mode):
    class FailureGateway:
        def pay(self, request):
            if mode == 'exception':
                raise PaymentError('declined')
            return PaymentReceipt('mock', 'bad', 1)
    app.extensions['payment_gateway'] = FailureGateway()
    key = prepare(client, product)
    assert checkout(client, key).status_code == 502
    assert db.session.query(CustomerOrder).count() == 0
    assert db.session.query(CartItem).one().quantity == 2 and product.stock == 3


def test_database_failure_rolls_back(client, product):
    from sqlalchemy.exc import OperationalError
    key = prepare(client, product)
    def fail(mapper, connection, target):
        raise OperationalError('synthetic failure', {}, Exception('test'))
    event.listen(CustomerOrder, 'before_insert', fail)
    try:
        assert checkout(client, key).status_code == 503
    finally:
        event.remove(CustomerOrder, 'before_insert', fail)
    assert db.session.query(CustomerOrder).count() == 0
    assert db.session.query(CartItem).one().quantity == 2 and product.stock == 3
    assert checkout(client, key).status_code == 302


def test_account_history_after_relogin(client, app, product):
    prepare(client, product)
    assert post(client, '/register', {'email': 'buyer@example.com', 'password': '12345678'}).status_code == 302
    assert '700,000 تومان' in client.get('/cart').get_data(as_text=True)
    client.get('/checkout')
    with client.session_transaction() as s:
        key = s['checkout']['key']
    response = checkout(client, key)
    purchase = db.session.query(CustomerOrder).one()
    assert purchase.user_id == db.session.query(User).one().id
    post(client, '/logout')
    assert client.get(response.location).status_code == 404
    post(client, '/login', {'email': 'buyer@example.com', 'password': '12345678'})
    assert client.get(response.location).status_code == 200
    assert purchase.tracking_code in client.get('/orders').get_data(as_text=True)
    other = app.test_client()
    post(other, '/register', {'email': 'other@example.com', 'password': '12345678'})
    assert other.get(response.location).status_code == 404


def test_two_buyers_cannot_oversell(client, app, product):
    first_key = prepare(client, product)
    other = app.test_client()
    second_key = prepare(other, product)
    assert checkout(client, first_key).status_code == 302
    assert checkout(other, second_key).status_code == 409
    assert db.session.query(CustomerOrder).count() == 1
    assert product.stock == 1


def test_concurrent_checkouts_use_sqlite_write_lock(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from app import create_app
    application = create_app({'TESTING': True, 'SECRET_KEY': 'parallel-test', 'SQLALCHEMY_DATABASE_URI': f'sqlite:///{tmp_path / "parallel.sqlite3"}'})
    with application.app_context():
        db.create_all()
        p = Product(name='آخرین لباس', price_toman=100, stock=1)
        db.session.add(p)
        db.session.commit()
        product_id = p.id
    clients = [application.test_client(), application.test_client()]
    keys = []
    for browser in clients:
        assert post(browser, '/cart/items', {'product_id': product_id, 'quantity': '1'}).status_code == 302
        browser.get('/checkout')
        with browser.session_transaction() as s:
            keys.append(s['checkout']['key'])
    barrier = Barrier(2)
    def submit(index):
        barrier.wait(timeout=10)
        return checkout(clients[index], keys[index]).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submit, [0, 1]))
    assert sorted(results) == [302, 409]
    with application.app_context():
        assert db.session.get(Product, product_id).stock == 0
        assert db.session.query(CustomerOrder).count() == 1


def test_price_change_requires_fresh_confirmation(client, product):
    key = prepare(client, product)
    product.price_toman = 400000
    db.session.commit()
    assert checkout(client, key).status_code == 409
    assert client.get('/checkout').status_code == 200
    with client.session_transaction() as s:
        fresh_key = s['checkout']['key']
    assert fresh_key != key
    assert checkout(client, fresh_key).status_code == 302
    assert db.session.query(CustomerOrder).one().total_toman == 800000
