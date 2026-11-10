"""Flask application factory and explicit database initialization."""
from pathlib import Path

import click
from flask import Flask
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

    @app.cli.command('upgrade-db')
    def upgrade_db():
        """Add stage 3 columns to an existing stage 2 SQLite database."""
        db.create_all()
        columns = {column['name'] for column in inspect(db.engine).get_columns('product')}
        with db.engine.begin() as connection:
            for column in ('category', 'size', 'color'):
                if column not in columns:
                    connection.execute(text(f"ALTER TABLE product ADD COLUMN {column} TEXT NOT NULL DEFAULT ''"))
        click.echo('Database upgraded.')

    return app


def _enable_foreign_keys(connection, _record):
    cursor = connection.cursor()
    cursor.execute('PRAGMA foreign_keys=ON')
    cursor.close()
