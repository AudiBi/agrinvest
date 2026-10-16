from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app import create_app
from app.extensions import db, db as _db
from app.models import Project, User
from app.models.enums import ProjectStatus, UserRole


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


@pytest.fixture()
def investor(app):
    user = User(email='inv@example.com', password='Passw0rd!x', role=UserRole.INVESTOR,
                name='Ines Investor', country='HT')
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def project(app):
    farmer = User(email='farm@example.com', password='Passw0rd!x', role=UserRole.FARMER,
                  name='Fred Farmer')
    db.session.add(farmer)
    db.session.flush()
    p = Project(title='Café', slug='cafe', description='d', amount_needed=Decimal('1000000'),
                farmer_id=farmer.id, status=ProjectStatus.PUBLISHED, is_published=True,
                min_investment=Decimal('100'), currency='HTG',
                deadline=datetime.now(timezone.utc) + timedelta(days=30))
    db.session.add(p)
    db.session.commit()
    return p
