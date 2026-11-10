"""Session-owned carts and atomic mock checkout."""
import re
import secrets

from flask import Blueprint, abort, current_app, g, redirect, render_template, request, session, url_for
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Cart, CartItem, CustomerOrder, OrderItem, Product
from app.services.payments import PaymentError, PaymentRequest

orders = Blueprint('orders', __name__)
MAX_INTEGER = 9223372036854775807


def get_cart():
    cart = db.session.get(Cart, session.get('cart_id', ''))
    if cart is None:
        cart = Cart()
        db.session.add(cart)
        db.session.commit()
        session['cart_id'] = cart.id
    return cart


def snapshot(cart):
    return [[item.product_id, item.quantity, item.product.price_toman] for item in sorted(cart.items, key=lambda i: i.product_id)]


def total(cart):
    return sum(item.quantity * item.product.price_toman for item in cart.items)


def error(message, status=400):
    return render_template('error.html', message=message), status


def quantity_value():
    value = request.form.get('quantity', '').strip()
    if not value.isdecimal():
        raise ValueError
    result = int(value)
    if not 1 <= result <= MAX_INTEGER:
        raise ValueError
    return result


@orders.get('/cart')
def cart_page():
    cart = get_cart()
    return render_template('cart.html', cart=cart, total=total(cart))


@orders.post('/cart/items')
def add_item():
    try:
        quantity = quantity_value()
        product_id = int(request.form.get('product_id', ''))
        if not 0 < product_id <= MAX_INTEGER:
            raise ValueError
    except ValueError:
        return error('محصول یا تعداد نامعتبر است.')
    cart = get_cart()
    product = db.session.get(Product, product_id)
    item = db.session.get(CartItem, (cart.id, product_id))
    count = quantity + (item.quantity if item else 0)
    if not product or not product.is_active or count > product.stock:
        return error('محصول فعال نیست یا موجودی کافی نیست.')
    if item:
        item.quantity = count
    else:
        db.session.add(CartItem(cart=cart, product=product, quantity=count))
    db.session.commit()
    session.pop('checkout', None)
    return redirect(url_for('orders.cart_page'))


@orders.post('/cart/items/<int:product_id>/update')
def update_item(product_id):
    cart = get_cart()
    item = next((i for i in cart.items if i.product_id == product_id), None)
    if item is None:
        abort(404)
    try:
        quantity = quantity_value()
    except ValueError:
        return error('تعداد باید عدد صحیح مثبت باشد.')
    if not item.product.is_active or quantity > item.product.stock:
        return error('موجودی کافی نیست.')
    item.quantity = quantity
    db.session.commit()
    session.pop('checkout', None)
    return redirect(url_for('orders.cart_page'))


@orders.post('/cart/items/<int:product_id>/delete')
def delete_item(product_id):
    cart = get_cart()
    item = next((i for i in cart.items if i.product_id == product_id), None)
    if item is None:
        abort(404)
    db.session.delete(item)
    db.session.commit()
    session.pop('checkout', None)
    return redirect(url_for('orders.cart_page'))


@orders.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart = get_cart()
    if request.method == 'GET':
        if not cart.items:
            return error('سبد خرید خالی است.')
        session['checkout'] = {'key': secrets.token_urlsafe(32), 'snapshot': snapshot(cart)}
        return render_template('checkout.html', cart=cart, total=total(cart), checkout_key=session['checkout']['key'])
    pending = session.get('checkout')
    if not pending or request.form.get('checkout_key') != pending['key']:
        return error('برای تأیید مبلغ، صفحه تکمیل خرید را دوباره باز کنید.', 409)
    name = request.form.get('recipient_name', '').strip()
    address = request.form.get('address', '').strip()
    phone = request.form.get('phone', '').strip().translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789'))
    if not 1 <= len(name) <= 100 or not 1 <= len(address) <= 1000 or not re.fullmatch(r'09[0-9]{9}', phone):
        return error('نام، نشانی و تلفن همراه معتبر وارد کنید.')
    cart_id = cart.id
    user_id = g.user.id if g.user else None
    # Discard read transaction and acquire the SQLite write lock before re-reading.
    db.session.rollback()
    try:
        db.session.execute(text('BEGIN IMMEDIATE'))
        existing = db.session.scalar(db.select(CustomerOrder).where(CustomerOrder.checkout_key == pending['key'], CustomerOrder.cart_id == cart_id))
        if existing:
            reference = existing.tracking_code
            db.session.rollback()
            return redirect(url_for('orders.confirmation', tracking_code=reference))
        cart = db.session.get(Cart, cart_id)
        if not cart.items or snapshot(cart) != pending['snapshot']:
            db.session.rollback()
            return error('سبد یا قیمت تغییر کرده است؛ مبلغ تازه را دوباره تأیید کنید.', 409)
        if any(not i.product.is_active or i.quantity > i.product.stock for i in cart.items):
            db.session.rollback()
            return error('موجودی کافی نیست؛ سبد را اصلاح کنید.', 409)
        amount = total(cart)
        if amount > MAX_INTEGER:
            db.session.rollback()
            return error('مبلغ سفارش بیش از حد مجاز است.')
        receipt = current_app.extensions['payment_gateway'].pay(PaymentRequest(amount, pending['key']))
        if receipt.amount_toman != amount or not receipt.reference or not receipt.provider:
            raise PaymentError('Receipt mismatch')
        purchase = CustomerOrder(cart=cart, user_id=user_id, checkout_key=pending['key'], recipient_name=name, phone=phone, address=address, total_toman=amount, status='mock_paid', payment_provider=receipt.provider, payment_reference=receipt.reference)
        for item in list(cart.items):
            purchase.items.append(OrderItem(product=item.product, product_name=item.product.name, unit_price_toman=item.product.price_toman, quantity=item.quantity))
            item.product.stock -= item.quantity
            db.session.delete(item)
        db.session.add(purchase)
        db.session.commit()
        return redirect(url_for('orders.confirmation', tracking_code=purchase.tracking_code))
    except PaymentError:
        db.session.rollback()
        return error('پرداخت آزمایشی ناموفق بود؛ دوباره تلاش کنید.', 502)
    except SQLAlchemyError:
        db.session.rollback()
        return error('ثبت سفارش ممکن نشد؛ دوباره تلاش کنید.', 503)


def owned_orders():
    if g.user:
        return db.select(CustomerOrder).where(CustomerOrder.user_id == g.user.id)
    return db.select(CustomerOrder).where(CustomerOrder.cart_id == session.get('cart_id', ''), CustomerOrder.user_id.is_(None))


@orders.get('/orders')
def history():
    purchases = db.session.scalars(owned_orders().order_by(CustomerOrder.id.desc())).all()
    return render_template('orders.html', purchases=purchases)


@orders.get('/orders/<tracking_code>')
def confirmation(tracking_code):
    purchase = db.session.scalar(owned_orders().where(CustomerOrder.tracking_code == tracking_code))
    if purchase is None:
        abort(404)
    return render_template('confirmation.html', purchase=purchase)
