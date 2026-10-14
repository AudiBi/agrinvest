import pytest

from app import create_app
from app.extensions import db as _db


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setenv('FLASK_ENV', 'testing')
    app = create_app('testing')
    app.config.update(
        MONCASH_WEBHOOK_SECRET='moncash-test-secret',
        WISE_WEBHOOK_SECRET='wise-test-secret',
    )
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
