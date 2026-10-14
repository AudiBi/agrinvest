import pytest

from app import create_app
from app.config import ProductionConfig


def test_production_requires_secret_key(monkeypatch):
    monkeypatch.setattr(ProductionConfig, 'SECRET_KEY', None)
    monkeypatch.setattr(ProductionConfig, 'SQLALCHEMY_DATABASE_URI', 'sqlite://')
    with pytest.raises(RuntimeError, match='SECRET_KEY'):
        create_app('production')


def test_production_requires_database_url(monkeypatch):
    monkeypatch.setattr(ProductionConfig, 'SECRET_KEY', 'x')
    monkeypatch.setattr(ProductionConfig, 'SQLALCHEMY_DATABASE_URI', None)
    with pytest.raises(RuntimeError, match='DATABASE_URL'):
        create_app('production')


def test_api_blueprints_are_registered(app):
    rules = {r.rule for r in app.url_map.iter_rules()}
    assert any(r.startswith('/api/v1/transfers') for r in rules)
    assert any(r.startswith('/api/v1/webhooks') for r in rules)
