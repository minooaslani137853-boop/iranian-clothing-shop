import pytest
from app import create_app
from app.config import TestingConfig
from app.extensions import db


@pytest.fixture
def app(tmp_path):
    application = create_app(TestingConfig)
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()
