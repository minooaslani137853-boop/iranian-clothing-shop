"""Administrator-only product, inventory and fulfillment management."""
from functools import wraps
from pathlib import PurePosixPath

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import CustomerOrder, Product

admin = Blueprint('admin', __name__, url_prefix='/admin')
MAX_INTEGER = 9223372036854775807
TRANSITIONS = {'placed': ('processing',), 'mock_paid': ('processing',), 'processing': ('shipped',), 'shipped': ('delivered',), 'delivered': ()}
STATUS_LABELS = {'placed': 'ثبت‌شده', 'mock_paid': 'پرداخت آزمایشی', 'processing': 'در حال آماده‌سازی', 'shipped': 'ارسال‌شده', 'delivered': 'تحویل‌شده'}


def admin_required(view):
    @wraps(view)
    def guarded(*args, **kwargs):
        if g.user is None:
            return redirect(url_for('shop.login'))
        if not g.user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return guarded


@admin.before_request
@admin_required
def protect_all_routes():
    return None


@admin.get('/')
def dashboard():
    return render_template('admin/dashboard.html', product_count=db.session.scalar(db.select(db.func.count(Product.id))), order_count=db.session.scalar(db.select(db.func.count(CustomerOrder.id))))


@admin.get('/products')
def products():
    return render_template('admin/products.html', products=db.session.scalars(db.select(Product).order_by(Product.id.desc())).all())


def product_values():
    values = {key: request.form.get(key, '').strip() for key in ('name', 'description', 'category', 'size', 'color', 'image_path')}
    if not values['name'] or len(values['name']) > 200:
        raise ValueError('نام محصول الزامی و حداکثر ۲۰۰ نویسه است.')
    if len(values['description']) > 5000 or any(len(values[k]) > 100 for k in ('category', 'size', 'color')):
        raise ValueError('توضیحات حداکثر ۵۰۰۰ و مشخصات حداکثر ۱۰۰ نویسه باشند.')
    path = values['image_path']
    if path and (len(path) > 300 or not path.startswith('images/') or '..' in PurePosixPath(path).parts or '\\' in path or '?' in path or '#' in path or PurePosixPath(path).suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp', '.avif'}):
        raise ValueError('مسیر تصویر باید فایل محلی مانند images/product.webp باشد.')
    for field in ('price_toman', 'stock'):
        value = request.form.get(field, '').strip()
        if not value.isdecimal() or len(value) > 19 or not 0 <= int(value) <= MAX_INTEGER:
            raise ValueError('قیمت و موجودی باید عدد صحیح نامنفی باشند.')
        values[field] = int(value)
    values['is_active'] = request.form.get('is_active') == '1'
    return values


@admin.route('/products/new', methods=['GET', 'POST'])
def create_product():
    return edit_product_form(None)


@admin.route('/products/<int:product_id>/edit', methods=['GET', 'POST'])
def edit_product(product_id):
    return edit_product_form(db.get_or_404(Product, product_id))


def edit_product_form(product):
    error = None
    if request.method == 'POST':
        try:
            values = product_values()
        except ValueError as exc:
            error = str(exc)
        else:
            if product is None:
                product = Product()
                db.session.add(product)
            for key, value in values.items():
                setattr(product, key, value)
            db.session.commit()
            flash('محصول با موفقیت ذخیره شد.', 'success')
            return redirect(url_for('admin.products'))
    return render_template('admin/product_form.html', product=product, error=error), 400 if error else 200


@admin.post('/products/<int:product_id>/delete')
def delete_product(product_id):
    product = db.get_or_404(Product, product_id)
    db.session.delete(product)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return render_template('error.html', code=409, message='این محصول در سبد یا سفارش استفاده شده است؛ به جای حذف، آن را غیرفعال کنید.'), 409
    flash('محصول حذف شد.', 'success')
    return redirect(url_for('admin.products'))


@admin.get('/orders')
def orders():
    return render_template('admin/orders.html', purchases=db.session.scalars(db.select(CustomerOrder).order_by(CustomerOrder.id.desc())).all(), labels=STATUS_LABELS)


@admin.route('/orders/<int:order_id>', methods=['GET', 'POST'])
def order_detail(order_id):
    purchase = db.get_or_404(CustomerOrder, order_id)
    if request.method == 'POST':
        target = request.form.get('status', '')
        allowed_sources = [source for source, targets in TRANSITIONS.items() if target in targets]
        # Conditional update also rejects stale forms and concurrent transitions.
        result = db.session.execute(db.update(CustomerOrder).where(CustomerOrder.id == order_id, CustomerOrder.status.in_(allowed_sources)).values(status=target))
        if result.rowcount != 1:
            db.session.rollback()
            return render_template('error.html', code=409, message='تغییر وضعیت مجاز نیست یا سفارش قبلاً تغییر کرده است.'), 409
        db.session.commit()
        flash('وضعیت سفارش به‌روز شد.', 'success')
        return redirect(url_for('admin.order_detail', order_id=order_id))
    return render_template('admin/order.html', purchase=purchase, transitions=TRANSITIONS.get(purchase.status, ()), labels=STATUS_LABELS)
