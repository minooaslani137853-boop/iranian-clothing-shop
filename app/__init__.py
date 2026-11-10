"""Flask application factory and explicit database initialization."""
from pathlib import Path

import click
from flask import Flask, render_template
from sqlalchemy import event, inspect, text

from app.config import Config
from app.extensions import db


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + str(
        Path(app.instance_path) / 'shop.sqlite3'
    )
    if config is not None:
        if isinstance(config, dict):
            app.config.from_mapping(config)
        else:
            app.config.from_object(config)
    if not app.config.get('SECRET_KEY'):
        from secrets import token_hex
        app.config['SECRET_KEY'] = token_hex(32)
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    from app import models  # noqa: F401: register model metadata

    with app.app_context():
        if db.engine.dialect.name == 'sqlite':
            event.listen(db.engine, 'connect', _enable_foreign_keys)

    @app.cli.command('init-db')
    def init_db():
        """Create missing tables without deleting existing data."""
        db.create_all()
        click.echo('Database initialized.')

    from app.routes.shop import shop
    app.register_blueprint(shop)
    from app.routes.orders import orders
    app.register_blueprint(orders)
    from app.routes.admin import admin
    app.register_blueprint(admin)

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('error.html', code=500, message='خطای داخلی رخ داده است. لطفاً کمی بعد دوباره تلاش کنید.'), 500

    @app.errorhandler(403)
    def forbidden(error):
        return render_template('error.html', code=403, message='اجازه دسترسی به این بخش را ندارید.'), 403

    @app.cli.command('set-admin')
    @click.option('--email', required=True, help='Email of an existing registered user.')
    @click.option('--revoke', is_flag=True, help='Remove administrator access.')
    def set_admin(email, revoke):
        from app.models import User
        user = db.session.scalar(db.select(User).where(User.email == email.strip().casefold()))
        if user is None:
            raise click.ClickException('User not found; register the account first.')
        user.is_admin = not revoke
        db.session.commit()
        click.echo('Administrator access updated.')
    from app.services.payments import MockGateway
    app.extensions['payment_gateway'] = app.config.get('PAYMENT_GATEWAY') or MockGateway()

    @app.cli.command('upgrade-db')
    def upgrade_db():
        """Upgrade stage 2/3 SQLite schemas without deleting existing data."""
        db.create_all()
        columns = {column['name'] for column in inspect(db.engine).get_columns('product')}
        with db.engine.begin() as connection:
            for column in ('category', 'size', 'color'):
                if column not in columns:
                    connection.execute(text(f"ALTER TABLE product ADD COLUMN {column} TEXT NOT NULL DEFAULT ''"))
        order_columns = {column['name'] for column in inspect(db.engine).get_columns('customer_order')}
        additions = {'user_id': 'INTEGER REFERENCES user(id) ON DELETE RESTRICT',
                     'payment_provider': "TEXT NOT NULL DEFAULT 'mock'",
                     'payment_reference': 'TEXT'}
        with db.engine.begin() as connection:
            for column, definition in additions.items():
                if column not in order_columns:
                    connection.execute(text(f'ALTER TABLE customer_order ADD COLUMN {column} {definition}'))
        user_columns = {column['name'] for column in inspect(db.engine).get_columns('user')}
        if 'is_admin' not in user_columns:
            with db.engine.begin() as connection:
                connection.execute(text('ALTER TABLE user ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0 CHECK (is_admin IN (0, 1))'))
        click.echo('Database upgraded.')

    return app


def _enable_foreign_keys(connection, _record):
    cursor = connection.cursor()
    cursor.execute('PRAGMA foreign_keys=ON')
    cursor.close()
