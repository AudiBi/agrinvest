from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app import create_app
from app.extensions import db, db as _db
from app.models import Project, User
from app.models.enums import ProjectStatus, UserRole


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch):
    """Hachage allégé pour les tests uniquement (le hachage de production, ~1 s, reste inchangé).

    check_password_hash lit la méthode dans le hash lui-même : la vérification fonctionne pareil.
    """
    from werkzeug.security import generate_password_hash as real_hash
    monkeypatch.setattr('app.models.user.generate_password_hash',
                        lambda password, method='pbkdf2:sha256': real_hash(password, method='pbkdf2:sha256:1000'))


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setenv('FLASK_ENV', 'testing')
    app = create_app('testing')
    app.config.update(
        SESSION_PROTECTION=None,  # les tests posent la session à la main (login_as), sans _id
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


def make_user(email, role=UserRole.INVESTOR, is_admin=False, name='Test User', **extra):
    user = User(email=email, password='Passw0rd!x', role=role, name=name, is_admin=is_admin, **extra)
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def admin(app):
    return make_user('admin@example.com', role=UserRole.ADMIN, is_admin=True, name='Admin')


@pytest.fixture()
def other_investor(app):
    return make_user('other@example.com', name='Other Investor')


@pytest.fixture()
def farmer_user(app):
    return make_user('farmer2@example.com', role=UserRole.FARMER, name='Other Farmer')


def login_as(client, user):
    # Le contexte d'application des tests reste ouvert : Flask-Login met l'utilisateur en cache
    # dans `g` entre deux requêtes du client, ce qui masquerait le changement de session.
    from flask import g
    g.pop('_login_user', None)
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True
    return client


@pytest.fixture()
def limited_app(monkeypatch):
    """Application avec le limiteur de débit réellement actif (stockage mémoire)."""
    from app.config import TestingConfig
    from app.extensions import limiter
    monkeypatch.setattr(TestingConfig, 'RATELIMIT_ENABLED', True)
    monkeypatch.setattr(TestingConfig, 'RATELIMIT_STORAGE_URI', 'memory://')
    app = create_app('testing')
    app.config['SESSION_PROTECTION'] = None
    with app.app_context():
        _db.create_all()
        limiter.reset()
        yield app
        _db.session.remove()
        _db.drop_all()
