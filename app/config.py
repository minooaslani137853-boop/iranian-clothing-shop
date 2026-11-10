"""Configuration shared by independently created applications."""
import os


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = 'testing-only-key'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
