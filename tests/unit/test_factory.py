from sqlalchemy import inspect
from app import create_app
from app.extensions import db


def test_init_db_is_repeatable_and_persistent(tmp_path):
    settings = {'TESTING': True, 'SECRET_KEY': 'test', 'SQLALCHEMY_DATABASE_URI': f'sqlite:///{tmp_path / "shop.sqlite3"}'}
    app = create_app(settings)
    runner = app.test_cli_runner()
    assert runner.invoke(args=['init-db']).exit_code == 0
    assert runner.invoke(args=['init-db']).exit_code == 0
    from app.models import Product
    with app.app_context():
        assert set(inspect(db.engine).get_table_names()) == {'product', 'cart', 'cart_item', 'customer_order', 'order_item'}
        db.session.add(Product(name='لباس', price_toman=100, stock=1))
        db.session.commit()
    second = create_app(settings)
    with second.app_context():
        assert db.session.query(Product).one().price_toman == 100
