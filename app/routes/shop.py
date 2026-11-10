"""Persian storefront and session authentication."""
import hmac
import re
import secrets
import unicodedata

from flask import Blueprint, abort, g, redirect, render_template, request, session, url_for
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models import Product, User

shop = Blueprint('shop', __name__)
DUMMY_HASH = generate_password_hash('not-a-real-user-password')


def normalize(value):
    return unicodedata.normalize('NFKC', value).translate(str.maketrans('يك', 'یک')).strip().casefold()


@shop.before_app_request
def prepare_request():
    g.user = db.session.get(User, session['user_id']) if session.get('user_id') else None
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_urlsafe(32)
    if request.method == 'POST':
        token = request.form.get('csrf_token', '')
        if not hmac.compare_digest(token.encode('utf-8'), session['csrf_token'].encode('utf-8')):
            abort(400, description='درخواست نامعتبر است؛ صفحه را تازه کنید.')


@shop.route('/')
def index():
    return redirect(url_for('shop.products'))


@shop.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip().casefold()
        password = request.form.get('password', '')
        if len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
            error = 'ایمیل معتبر وارد کنید.'
        elif not 8 <= len(password) <= 128:
            error = 'رمز عبور باید بین ۸ تا ۱۲۸ نویسه باشد.'
        else:
            user = User(email=email)
            user.set_password(password)
            db.session.add(user)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                error = 'این ایمیل قبلاً ثبت شده است.'
            else:
                cart_id = session.get('cart_id')
                session.clear()
                if cart_id:
                    session['cart_id'] = cart_id
                session['user_id'] = user.id
                return redirect(url_for('shop.products'))
    return render_template('auth.html', registering=True, error=error), 400 if error else 200


@shop.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip().casefold()
        password = request.form.get('password', '')
        user = db.session.scalar(db.select(User).where(User.email == email))
        valid = check_password_hash(user.password_hash if user else DUMMY_HASH, password) if len(password) <= 128 else False
        if user and valid:
            cart_id = session.get('cart_id')
            session.clear()
            if cart_id:
                session['cart_id'] = cart_id
            session['user_id'] = user.id
            return redirect(url_for('shop.products'))
        error = 'ایمیل یا رمز عبور نادرست است.'
    return render_template('auth.html', registering=False, error=error), 400 if error else 200


@shop.post('/logout')
def logout():
    session.clear()
    return redirect(url_for('shop.products'))


@shop.get('/products')
def products():
    filters = {key: request.args.get(key, '').strip() for key in ('q', 'category', 'size', 'color', 'min_price', 'max_price')}
    query = db.select(Product).where(Product.is_active.is_(True))
    error = None
    bounds = {}
    for key in ('min_price', 'max_price'):
        value = filters[key]
        if value:
            try:
                number = int(value)
                if number < 0 or number > 9223372036854775807:
                    raise ValueError
                bounds[key] = number
            except ValueError:
                error = 'قیمت باید عدد صحیح نامنفی باشد.'
    if bounds.get('min_price', 0) > bounds.get('max_price', 9223372036854775807):
        error = 'حداقل قیمت نباید بیشتر از حداکثر باشد.'
    for key in ('category', 'size', 'color'):
        if filters[key]:
            query = query.where(getattr(Product, key) == filters[key])
    if 'min_price' in bounds:
        query = query.where(Product.price_toman >= bounds['min_price'])
    if 'max_price' in bounds:
        query = query.where(Product.price_toman <= bounds['max_price'])
    results = [] if error else list(db.session.scalars(query.order_by(Product.id)))
    if filters['q']:
        term = normalize(filters['q'])
        results = [p for p in results if term in normalize(p.name + ' ' + p.description)]
    options = {key: list(db.session.scalars(db.select(getattr(Product, key)).where(Product.is_active.is_(True), getattr(Product, key) != '').distinct().order_by(getattr(Product, key)))) for key in ('category', 'size', 'color')}
    return render_template('products.html', products=results, filters=filters, options=options, error=error), 400 if error else 200


@shop.get('/products/<int:product_id>')
def product_detail(product_id):
    product = db.session.get(Product, product_id)
    if product is None or not product.is_active:
        abort(404)
    return render_template('product.html', product=product)


@shop.app_errorhandler(404)
def not_found(_error):
    return render_template('error.html', message='صفحه یا محصول یافت نشد.'), 404


@shop.app_errorhandler(400)
def bad_request(_error):
    return render_template('error.html', message='درخواست نامعتبر است؛ اطلاعات را بررسی و صفحه را تازه کنید.'), 400
