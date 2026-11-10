import sqlite3

import pytest
from sqlalchemy import inspect

from app import create_app
from app.extensions import db
from app.models import Cart, CustomerOrder, OrderItem, Product, User

pytestmark = pytest.mark.integration


def post(client, path, data=None):
    client.get('/products')
    with client.session_transaction() as s:
        token = s['csrf_token']
    return client.post(path, data={**(data or {}), 'csrf_token': token})


@pytest.fixture
def admin_client(app):
    user = User(email='admin@example.com', is_admin=True)
    user.set_password('admin-test-password')
    db.session.add(user)
    db.session.commit()
    client = app.test_client()
    assert post(client, '/login', {'email': user.email, 'password': 'admin-test-password'}).status_code == 302
    return client


@pytest.fixture
def product(app):
    p = Product(name='مانتو', price_toman=350000, stock=5)
    db.session.add(p)
    db.session.commit()
    return p


@pytest.fixture
def purchase(product):
    order = CustomerOrder(cart=Cart(), recipient_name='گیرنده آزمایشی', phone='09123456789', address='نشانی آزمایشی', total_toman=350000, status='mock_paid')
    order.items.append(OrderItem(product=product, product_name=product.name, unit_price_toman=350000, quantity=1))
    db.session.add(order)
    db.session.commit()
    return order


def values(**overrides):
    return {'name': 'پیراهن ایرانی', 'description': 'پنبه', 'price_toman': '250000', 'stock': '4', 'category': 'پیراهن', 'size': 'M', 'color': 'آبی', 'image_path': '', 'is_active': '1', **overrides}


@pytest.mark.parametrize('path', ['/admin/', '/admin/products', '/admin/products/new', '/admin/products/1/edit', '/admin/orders', '/admin/orders/1'])
def test_admin_read_routes_reject_guests_and_customers(app, path):
    client = app.test_client()
    assert client.get(path).status_code == 302
    post(client, '/register', {'email': 'customer@example.com', 'password': '12345678', 'is_admin': '1'})
    user = db.session.query(User).one()
    assert user.is_admin is False
    assert client.get(path).status_code == 403


@pytest.mark.parametrize('path', ['/admin/products/new', '/admin/products/1/edit', '/admin/products/1/delete', '/admin/orders/1'])
def test_admin_write_routes_reject_nonadmins(app, product, path):
    client = app.test_client()
    assert post(client, path, values()).status_code == 302
    post(client, '/register', {'email': 'ordinary@example.com', 'password': '12345678'})
    assert post(client, path, values()).status_code == 403
    assert db.session.get(Product, product.id).name == 'مانتو'


def test_product_crud_and_inventory(admin_client):
    client = admin_client
    assert client.get('/admin/').status_code == 200
    assert post(client, '/admin/products/new', values()).status_code == 302
    p = db.session.query(Product).one()
    assert p.stock == 4 and p.price_toman == 250000
    assert 'پیراهن ایرانی' in client.get('/products').get_data(as_text=True)
    assert '250,000 تومان' in client.get('/admin/products').get_data(as_text=True)
    assert client.get(f'/admin/products/{p.id}/edit').status_code == 200
    assert post(client, f'/admin/products/{p.id}/edit', values(stock='0', price_toman='300000', is_active='')).status_code == 302
    assert p.stock == 0 and p.price_toman == 300000 and p.is_active is False
    assert 'پیراهن ایرانی' not in client.get('/products').get_data(as_text=True)
    assert post(client, f'/admin/products/{p.id}/delete').status_code == 302
    assert db.session.query(Product).count() == 0


@pytest.mark.parametrize('overrides', [{'name': ''}, {'price_toman': '-1'}, {'stock': '1.5'}, {'stock': str(2**64)}, {'stock': '9' * 5000}, {'description': 'x' * 5001}, {'category': 'x' * 101}, {'image_path': 'https://example.com/a.png'}, {'image_path': 'images/../secret.png'}, {'image_path': 'images/bad.svg'}])
def test_product_validation_preserves_existing_data(admin_client, product, overrides):
    assert post(admin_client, f'/admin/products/{product.id}/edit', values(**overrides)).status_code == 400
    db.session.refresh(product)
    assert product.name == 'مانتو' and product.stock == 5


def test_history_prevents_delete_and_preserves_snapshot(admin_client, purchase, product):
    assert post(admin_client, f'/admin/products/{product.id}/delete').status_code == 409
    assert db.session.get(Product, product.id) is not None
    assert post(admin_client, f'/admin/products/{product.id}/edit', values()).status_code == 302
    assert purchase.items[0].product_name == 'مانتو' and purchase.items[0].unit_price_toman == 350000


def test_order_management_valid_transitions(admin_client, purchase, product):
    client = admin_client
    assert 'گیرنده آزمایشی' in client.get('/admin/orders').get_data(as_text=True)
    assert 'نشانی آزمایشی' in client.get(f'/admin/orders/{purchase.id}').get_data(as_text=True)
    for status in ['processing', 'shipped', 'delivered']:
        assert post(client, f'/admin/orders/{purchase.id}', {'status': status}).status_code == 302
        db.session.refresh(purchase)
        assert purchase.status == status
    assert product.stock == 5 and purchase.total_toman == 350000
    assert post(client, f'/admin/orders/{purchase.id}', {'status': 'mock_paid'}).status_code == 409


def test_order_status_rejects_skips_and_repeats(admin_client, purchase):
    path = f'/admin/orders/{purchase.id}'
    assert post(admin_client, path, {'status': 'delivered'}).status_code == 409
    assert post(admin_client, path, {'status': 'paid'}).status_code == 409
    assert post(admin_client, path, {'status': 'processing'}).status_code == 302
    assert post(admin_client, path, {'status': 'processing'}).status_code == 409


@pytest.mark.parametrize('path', ['/admin/products/new', '/admin/products/1/edit', '/admin/products/1/delete', '/admin/orders/1'])
def test_admin_csrf(admin_client, product, path):
    assert admin_client.post(path, data=values()).status_code == 400
    assert db.session.get(Product, product.id).name == 'مانتو'


def test_role_revocation_takes_effect_immediately(admin_client):
    user = db.session.query(User).one()
    user.is_admin = False
    db.session.commit()
    assert admin_client.get('/admin/').status_code == 403


def test_admin_cli_promotes_and_revokes_existing_user(app):
    user = User(email='member@example.com')
    user.set_password('test-password')
    db.session.add(user)
    db.session.commit()
    runner = app.test_cli_runner()
    assert runner.invoke(args=['set-admin', '--email', 'MEMBER@example.com']).exit_code == 0
    db.session.refresh(user)
    assert user.is_admin
    assert runner.invoke(args=['set-admin', '--email', user.email, '--revoke']).exit_code == 0
    db.session.refresh(user)
    assert not user.is_admin
    assert runner.invoke(args=['set-admin', '--email', 'missing@example.com']).exit_code != 0


def test_upgrade_existing_users_does_not_grant_admin(tmp_path):
    path = tmp_path / 'stage4.sqlite3'
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE user (id INTEGER PRIMARY KEY, email VARCHAR(254) NOT NULL UNIQUE, password_hash TEXT NOT NULL, created_at TEXT NOT NULL)')
        connection.execute("INSERT INTO user VALUES (1, 'old@example.com', 'existing-hash', '2026-11-10')")
    application = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': f'sqlite:///{path}'})
    runner = application.test_cli_runner()
    assert runner.invoke(args=['upgrade-db']).exit_code == 0
    assert runner.invoke(args=['upgrade-db']).exit_code == 0
    with application.app_context():
        user = db.session.get(User, 1)
        assert user.is_admin is False and user.password_hash == 'existing-hash'
        assert 'is_admin' in {c['name'] for c in inspect(db.engine).get_columns('user')}


def test_farsi_404_and_500_hide_internal_errors():
    application = create_app({'TESTING': True, 'PROPAGATE_EXCEPTIONS': False})
    @application.get('/intentional-error')
    def broken():
        raise RuntimeError('PRIVATE_INTERNAL_DETAIL')
    with application.app_context():
        db.create_all()
    client = application.test_client()
    response = client.get('/missing-page')
    assert response.status_code == 404 and 'صفحه یا محصول یافت نشد' in response.get_data(as_text=True)
    response = client.get('/intentional-error')
    assert response.status_code == 500
    html = response.get_data(as_text=True)
    assert 'خطای داخلی' in html and 'PRIVATE_INTERNAL_DETAIL' not in html
    assert 'lang="fa" dir="rtl"' in html
