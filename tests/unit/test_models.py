from datetime import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import Cart, CartItem, CustomerOrder, OrderItem, Product

pytestmark = pytest.mark.unit


def product():
    value = Product(name='مانتو ایرانی', price_toman=350000, stock=3)
    db.session.add(value)
    db.session.flush()
    return value


def order(cart):
    return CustomerOrder(cart=cart, recipient_name='گیرنده آزمایشی', phone='09123456789', address='نشانی آزمایشی', total_toman=700000)


def test_defaults_and_relationships(app):
    p = product()
    cart = Cart()
    cart.items.append(CartItem(product=p, quantity=2))
    purchase = order(cart)
    purchase.items.append(OrderItem(product=p, product_name=p.name, unit_price_toman=p.price_toman, quantity=2))
    db.session.add_all([cart, purchase])
    db.session.commit()
    assert p.is_active is True
    assert purchase.status == 'placed'
    assert cart.items[0].product is p
    assert purchase.items[0].line_total_toman == purchase.total_toman == 700000
    assert purchase.cart is cart
    assert len({cart.id, purchase.checkout_key, purchase.tracking_code}) == 3
    assert datetime.fromisoformat(purchase.created_at).utcoffset().total_seconds() == 0
    p.name, p.price_toman = 'نام تازه', 900000
    db.session.commit()
    db.session.expire_all()
    assert purchase.items[0].product_name == 'مانتو ایرانی'
    assert purchase.items[0].unit_price_toman == 350000


@pytest.mark.parametrize('field,value', [('price_toman', -1), ('price_toman', 1.5), ('stock', -1), ('stock', 1.5)])
def test_product_constraints(app, field, value):
    p = Product(name='لباس', price_toman=100, stock=1)
    setattr(p, field, value)
    db.session.add(p)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    assert db.session.query(Product).count() == 0


@pytest.mark.parametrize('quantity', [0, -1, 1.5])
def test_cart_quantity_constraint(app, quantity):
    p = product()
    db.session.add(Cart(items=[CartItem(product=p, quantity=quantity)]))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_duplicate_cart_product(app):
    p = product()
    c = Cart()
    db.session.add(c)
    db.session.flush()
    db.session.add_all([CartItem(cart_id=c.id, product_id=p.id, quantity=1), CartItem(cart_id=c.id, product_id=p.id, quantity=2)])
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_cart_delete_cascades_items(app):
    p = product()
    c = Cart(items=[CartItem(product=p, quantity=1)])
    db.session.add(c)
    db.session.commit()
    db.session.delete(c)
    db.session.commit()
    assert db.session.query(CartItem).count() == 0
    assert db.session.get(Product, p.id) is p


@pytest.mark.parametrize('target', ['cart', 'product'])
def test_order_history_prevents_parent_delete(app, target):
    p = product()
    c = Cart()
    purchase = order(c)
    purchase.items.append(OrderItem(product=p, product_name=p.name, unit_price_toman=350000, quantity=2))
    db.session.add(purchase)
    db.session.commit()
    db.session.delete(c if target == 'cart' else p)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    assert db.session.query(OrderItem).count() == 1


@pytest.mark.parametrize('field', ['checkout_key', 'tracking_code'])
def test_order_keys_unique(app, field):
    c = Cart()
    first, second = order(c), order(c)
    setattr(first, field, 'duplicate')
    setattr(second, field, 'duplicate')
    db.session.add_all([first, second])
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


@pytest.mark.parametrize('field,value', [('quantity', 0), ('quantity', 1.5), ('unit_price_toman', -1), ('unit_price_toman', 1.5)])
def test_order_item_constraints(app, field, value):
    p = product()
    item = OrderItem(product=p, product_name=p.name, unit_price_toman=350000, quantity=2)
    setattr(item, field, value)
    purchase = order(Cart())
    purchase.items.append(item)
    db.session.add(purchase)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


@pytest.mark.parametrize('total', [-1, 1.5])
def test_order_total_constraint(app, total):
    purchase = order(Cart())
    purchase.total_toman = total
    db.session.add(purchase)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_foreign_keys_enabled_on_new_connections(app):
    assert db.session.execute(text('PRAGMA foreign_keys')).scalar() == 1
    db.session.add(CartItem(cart_id='missing', product_id=999, quantity=1))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    db.session.remove()
    db.engine.dispose()
    assert db.session.execute(text('PRAGMA foreign_keys')).scalar() == 1


def test_factory_isolates_apps(app):
    product()
    db.session.commit()
    other = create_app(TestingConfig)
    with other.app_context():
        db.create_all()
        assert db.session.query(Product).count() == 0
    assert db.session.query(Product).count() == 1
