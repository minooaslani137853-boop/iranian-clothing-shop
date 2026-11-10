import sqlite3

import pytest
from sqlalchemy import inspect

from app import create_app
from app.extensions import db
from app.models import Product, User

pytestmark = pytest.mark.integration


@pytest.fixture
def client(app):
    return app.test_client()


def post(client, path, data):
    client.get(path if path != '/logout' else '/products')
    with client.session_transaction() as session:
        token = session['csrf_token']
    return client.post(path, data={**data, 'csrf_token': token})


@pytest.fixture
def catalog(app):
    products = [
        Product(name='مانتو ایرانی', description='پنبه خنک', category='مانتو', size='M', color='آبی', price_toman=350000, stock=3),
        Product(name='پیراهن', description='کتان', category='پیراهن', size='L', color='سفید', price_toman=500000, stock=0),
        Product(name='مانتو پنهان', category='مانتو', size='M', color='آبی', price_toman=300000, stock=1, is_active=False),
    ]
    db.session.add_all(products)
    db.session.commit()
    return products


def test_register_hash_login_logout(client):
    response = post(client, '/register', {'email': ' Test@Example.com ', 'password': 'strong-password'})
    assert response.status_code == 302
    user = db.session.scalar(db.select(User))
    assert user.email == 'test@example.com'
    assert user.password_hash != 'strong-password'
    assert user.password_hash.startswith('scrypt:')
    assert user.check_password('strong-password')
    with client.session_transaction() as session:
        assert session['user_id'] == user.id
    assert post(client, '/logout', {}).status_code == 302
    with client.session_transaction() as session:
        assert 'user_id' not in session
    assert post(client, '/login', {'email': 'TEST@example.com', 'password': 'strong-password'}).status_code == 302
    page = client.get('/products').get_data(as_text=True)
    assert 'test@example.com' in page and 'خروج' in page
    assert 'strong-password' not in page


@pytest.mark.parametrize('email,password', [('invalid', '12345678'), ('x@y.ir', 'short'), ('x@y.ir', 'x' * 129), ('', '')])
def test_registration_validation(client, email, password):
    assert post(client, '/register', {'email': email, 'password': password}).status_code == 400
    assert db.session.scalar(db.select(db.func.count(User.id))) == 0


def test_duplicate_registration(client):
    data = {'email': 'x@example.com', 'password': '12345678'}
    assert post(client, '/register', data).status_code == 302
    assert post(client, '/register', {**data, 'email': 'X@example.com'}).status_code == 400
    assert db.session.scalar(db.select(db.func.count(User.id))) == 1


@pytest.mark.parametrize('email,password', [('x@example.com', 'incorrect'), ('missing@example.com', '12345678')])
def test_login_failure_generic_and_no_session(client, email, password):
    post(client, '/register', {'email': 'x@example.com', 'password': '12345678'})
    post(client, '/logout', {})
    response = post(client, '/login', {'email': email, 'password': password})
    assert response.status_code == 400
    assert 'ایمیل یا رمز عبور نادرست است.' in response.get_data(as_text=True)
    with client.session_transaction() as session:
        assert 'user_id' not in session


@pytest.mark.parametrize('path', ['/register', '/login', '/logout'])
def test_csrf_required(client, path):
    assert client.post(path, data={'email': 'x@y.ir', 'password': '12345678'}).status_code == 400
    assert db.session.scalar(db.select(db.func.count(User.id))) == 0


def test_login_rotates_csrf_and_isolates_session(client, app):
    client.get('/login')
    with client.session_transaction() as session:
        old = session['csrf_token']
        session['untrusted'] = 'discard'
    post(client, '/register', {'email': 'x@y.ir', 'password': '12345678'})
    client.get('/products')
    with client.session_transaction() as session:
        assert session['csrf_token'] != old
        assert 'untrusted' not in session
    assert client.post('/logout', data={'csrf_token': old}).status_code == 400
    assert 'x@y.ir' not in app.test_client().get('/products').get_data(as_text=True)
    assert client.get('/logout').status_code == 405


def test_product_listing_and_details(client, catalog):
    response = client.get('/products')
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'lang="fa" dir="rtl"' in html
    assert 'مانتو ایرانی' in html and 'پیراهن' in html
    assert 'مانتو پنهان' not in html
    assert '350,000 تومان' in html
    detail = client.get(f'/products/{catalog[0].id}').get_data(as_text=True)
    assert 'پنبه خنک' in detail and 'آبی' in detail
    assert client.get(f'/products/{catalog[2].id}').status_code == 404
    assert client.get('/products/9999').status_code == 404
    assert client.get('/').location.endswith('/products')


@pytest.mark.parametrize('query', [
    {'q': 'ايراني'}, {'q': ' پنبه '}, {'category': 'مانتو'}, {'size': 'M'}, {'color': 'آبی'},
    {'min_price': '۳۵۰۰۰۰', 'max_price': '۳۵۰۰۰۰'},
    {'q': 'مانتو', 'category': 'مانتو', 'size': 'M', 'color': 'آبی', 'min_price': '350000', 'max_price': '400000'},
])
def test_search_and_filters(client, catalog, query):
    response = client.get('/products', query_string=query)
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert f'href="/products/{catalog[0].id}"' in html
    assert f'href="/products/{catalog[1].id}"' not in html
    assert 'مانتو پنهان' not in html


@pytest.mark.parametrize('query', [{'q': 'ناشناخته'}, {'q': "' OR 1=1 --"}, {'q': '%'}, {'category': 'مانتو', 'size': 'L'}])
def test_no_results_and_literal_search(client, catalog, query):
    response = client.get('/products', query_string=query)
    assert response.status_code == 200
    assert 'محصولی یافت نشد' in response.get_data(as_text=True)


@pytest.mark.parametrize('query', [{'min_price': '-1'}, {'max_price': '1.5'}, {'min_price': 'abc'}, {'max_price': str(2**64)}, {'min_price': '20', 'max_price': '10'}])
def test_invalid_price_returns_validation_error(client, catalog, query):
    assert client.get('/products', query_string=query).status_code == 400


def test_escaped_product_and_query(client, catalog):
    catalog[0].name = '<script>alert(1)</script>'
    db.session.commit()
    for response in [client.get('/products'), client.get(f'/products/{catalog[0].id}'), client.get('/products', query_string={'q': '<script>'})]:
        html = response.get_data(as_text=True)
        assert '<script>' not in html
        assert '&lt;script&gt;' in html


def test_empty_catalog(client):
    assert 'محصولی یافت نشد' in client.get('/products').get_data(as_text=True)


def test_upgrade_stage_two_database_preserves_data(tmp_path):
    path = tmp_path / 'old.sqlite3'
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE product (id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL, image_path TEXT NOT NULL, price_toman INTEGER NOT NULL, stock INTEGER NOT NULL, is_active BOOLEAN NOT NULL)')
        connection.execute("INSERT INTO product VALUES (1, 'legacy', '', '', 100, 1, 1)")
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test', 'SQLALCHEMY_DATABASE_URI': f'sqlite:///{path}'})
    runner = app.test_cli_runner()
    assert runner.invoke(args=['upgrade-db']).exit_code == 0
    assert runner.invoke(args=['upgrade-db']).exit_code == 0
    with app.app_context():
        p = db.session.get(Product, 1)
        assert p.name == 'legacy' and p.price_toman == 100
        assert p.category == p.size == p.color == ''
        assert 'user' in inspect(db.engine).get_table_names()
        order_columns = {c['name'] for c in inspect(db.engine).get_columns('customer_order')}
        assert {'user_id', 'payment_reference', 'payment_provider'} <= order_columns


def test_non_ascii_csrf_is_rejected(client):
    client.get('/register')
    assert client.post('/register', data={'csrf_token': 'نامعتبر'}).status_code == 400
