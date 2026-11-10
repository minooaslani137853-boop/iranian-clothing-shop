"""Relational entities; all monetary values are integer toman."""
from datetime import datetime, timezone
from secrets import token_urlsafe

from sqlalchemy import CheckConstraint

from app.extensions import db


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def random_key():
    return token_urlsafe(32)


class Product(db.Model):
    __tablename__ = 'product'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=False, default='')
    image_path = db.Column(db.Text, nullable=False, default='')
    price_toman = db.Column(db.Integer, nullable=False)
    category = db.Column(db.Text, nullable=False, default='')
    size = db.Column(db.Text, nullable=False, default='')
    color = db.Column(db.Text, nullable=False, default='')
    stock = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean(create_constraint=True, name='valid_active'), nullable=False, default=True)
    __table_args__ = (
        CheckConstraint("typeof(price_toman) = 'integer' AND price_toman >= 0", name='valid_price'),
        CheckConstraint("typeof(stock) = 'integer' AND stock >= 0", name='valid_stock'),
    )


class Cart(db.Model):
    __tablename__ = 'cart'
    id = db.Column(db.Text, primary_key=True, default=random_key)
    created_at = db.Column(db.Text, nullable=False, default=utc_now)
    items = db.relationship('CartItem', back_populates='cart', cascade='all, delete-orphan', passive_deletes=True)
    orders = db.relationship('CustomerOrder', back_populates='cart', passive_deletes='all')


class CartItem(db.Model):
    __tablename__ = 'cart_item'
    cart_id = db.Column(db.Text, db.ForeignKey('cart.id', ondelete='CASCADE'), primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id', ondelete='RESTRICT'), primary_key=True)
    quantity = db.Column(db.Integer, nullable=False)
    cart = db.relationship('Cart', back_populates='items')
    product = db.relationship('Product')
    __table_args__ = (CheckConstraint("typeof(quantity) = 'integer' AND quantity > 0", name='positive_quantity'),)


class CustomerOrder(db.Model):
    __tablename__ = 'customer_order'
    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Text, db.ForeignKey('cart.id', ondelete='RESTRICT'), nullable=False)
    checkout_key = db.Column(db.Text, nullable=False, unique=True, default=random_key)
    tracking_code = db.Column(db.Text, nullable=False, unique=True, default=random_key)
    recipient_name = db.Column(db.Text, nullable=False)
    phone = db.Column(db.Text, nullable=False)
    address = db.Column(db.Text, nullable=False)
    status = db.Column(db.Text, nullable=False, default='placed')
    total_toman = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.Text, nullable=False, default=utc_now)
    cart = db.relationship('Cart', back_populates='orders')
    items = db.relationship('OrderItem', back_populates='order', cascade='all, delete-orphan', passive_deletes=True)
    __table_args__ = (CheckConstraint("typeof(total_toman) = 'integer' AND total_toman >= 0", name='valid_total'),)


class OrderItem(db.Model):
    __tablename__ = 'order_item'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('customer_order.id', ondelete='CASCADE'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id', ondelete='RESTRICT'), nullable=False)
    product_name = db.Column(db.Text, nullable=False)
    unit_price_toman = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    order = db.relationship('CustomerOrder', back_populates='items')
    product = db.relationship('Product')
    __table_args__ = (
        CheckConstraint("typeof(unit_price_toman) = 'integer' AND unit_price_toman >= 0", name='valid_price'),
        CheckConstraint("typeof(quantity) = 'integer' AND quantity > 0", name='positive_quantity'),
    )

    @property
    def line_total_toman(self):
        return self.unit_price_toman * self.quantity


class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), nullable=False, unique=True)
    password_hash = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.Text, nullable=False, default=utc_now)

    def set_password(self, password):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)
