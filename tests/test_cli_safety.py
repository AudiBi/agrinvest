"""Mise en production : création du premier administrateur et garde-fous contre l'effacement de la base."""
import os
import subprocess
import sys

import pytest

from app.extensions import db
from app.models import AuditLog, User
from app.models.enums import UserRole
from app.utils.safety import CONFIRM_VARIABLE, check_safe_to_wipe

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSWORD = 'Passw0rd!x'


# ============================================================ garde-fou d'effacement
@pytest.mark.parametrize('uri,environ,allowed', [
    ('sqlite:///instance/dev.db', {}, True),
    ('sqlite://', {}, True),
    ('postgresql://u:p@localhost/agrinvest', {}, False),                       # locale, sans confirmation
    ('postgresql://u:p@localhost/agrinvest', {CONFIRM_VARIABLE: 'no'}, False),
    ('postgresql://u:p@localhost/agrinvest', {CONFIRM_VARIABLE: 'yes'}, True),
    ('postgresql://u:p@127.0.0.1:5432/agrinvest', {CONFIRM_VARIABLE: 'yes'}, True),
    ('postgresql://u:p@db.production.example/agrinvest', {CONFIRM_VARIABLE: 'yes'}, False),  # distante: jamais
    ('postgresql://u:p@localhost.evil.example/agrinvest', {CONFIRM_VARIABLE: 'yes'}, False),  # faux « localhost »
    ('postgresql://localhost@evil.example/agrinvest', {CONFIRM_VARIABLE: 'yes'}, False),       # « localhost » = identifiant
    ('', {CONFIRM_VARIABLE: 'yes'}, False),
    (None, {CONFIRM_VARIABLE: 'yes'}, False)])
def test_wipe_guard(uri, environ, allowed):
    assert check_safe_to_wipe(uri, environ)[0] is allowed


def run_init_db(database_url, **extra_env):
    env = {**os.environ, 'DATABASE_URL': database_url, 'FLASK_ENV': 'development', **extra_env}
    env.pop(CONFIRM_VARIABLE, None) if CONFIRM_VARIABLE not in extra_env else None
    return subprocess.run([sys.executable, 'init_db.py'], cwd=ROOT, env=env, capture_output=True,
                          text=True, timeout=120)


def test_init_db_script_refuses_a_remote_database_before_touching_it():
    result = run_init_db('postgresql://user:secret@db.production.example:5432/agrinvest',
                         **{CONFIRM_VARIABLE: 'yes'})
    assert result.returncode == 1
    assert 'distante' in result.stdout
    assert 'Suppression des données' not in result.stdout  # aucune étape destructrice n'a commencé


def test_init_db_script_refuses_a_local_postgres_without_confirmation():
    result = run_init_db('postgresql://user:secret@localhost:5432/agrinvest')
    assert result.returncode == 1 and CONFIRM_VARIABLE in result.stdout


# =============================================================== flask init-db
def test_init_db_command_refuses_to_bypass_migrations_on_postgres(app):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://u:p@db.example/agrinvest'
    result = app.test_cli_runner().invoke(args=['init-db'])
    assert result.exit_code != 0 and 'flask db upgrade' in result.output


def test_init_db_command_still_works_on_sqlite(app):
    if not str(app.config['SQLALCHEMY_DATABASE_URI']).startswith('sqlite'):
        pytest.skip('base de test PostgreSQL')
    assert app.test_cli_runner().invoke(args=['init-db']).exit_code == 0


# ============================================================== flask create-admin
def create_admin(app, email='Chef@Example.com', password=PASSWORD, confirm=None, name='Chef'):
    confirm = password if confirm is None else confirm
    return app.test_cli_runner().invoke(
        args=['create-admin', '--email', email, '--name', name], input=f'{password}\n{confirm}\n')


def test_create_admin_succeeds_and_never_prints_the_password(app):
    result = create_admin(app)
    assert result.exit_code == 0, result.output
    assert PASSWORD not in result.output
    user = User.query.filter_by(email='chef@example.com').one()  # adresse normalisée en minuscules
    assert (user.role, user.is_admin, user.is_verified, user.is_active) == (UserRole.ADMIN, True, True, True)
    assert user.email_verified_at is not None
    assert user.check_password(PASSWORD) and PASSWORD not in user.password_hash


def test_create_admin_is_audited_without_secrets(app):
    create_admin(app)
    entry = AuditLog.query.filter_by(action='user.admin_created').one()
    assert entry.actor_id is None and entry.target_type == 'users' and '"via": "cli"' in entry.details
    assert PASSWORD not in (entry.details or '')


@pytest.mark.parametrize('password', ['court', 'toutenminuscule1', 'SANSCHIFFRE', 'password'])
def test_create_admin_rejects_weak_passwords(app, password):
    result = create_admin(app, password=password)
    assert result.exit_code != 0 and 'faible' in result.output
    assert User.query.filter_by(is_admin=True).count() == 0


def test_create_admin_requires_matching_confirmation(app):
    result = create_admin(app, confirm='Autre1Passw0rd')
    assert User.query.filter_by(is_admin=True).count() == 0
    assert PASSWORD not in result.output


@pytest.mark.parametrize('email', ['pas-un-email', 'a@', '@b.com', ''])
def test_create_admin_rejects_invalid_emails(app, email):
    result = create_admin(app, email=email)
    assert result.exit_code != 0 and User.query.filter_by(is_admin=True).count() == 0


def test_create_admin_refuses_an_existing_address(app, investor):
    result = create_admin(app, email=investor.email.upper())
    assert result.exit_code != 0 and 'existe déjà' in result.output
    assert db.session.get(User, investor.id).is_admin is False  # le compte existant n'est jamais promu


def test_create_admin_non_interactive_mode(app, monkeypatch):
    monkeypatch.setenv('AGRINVEST_ADMIN_PASSWORD', PASSWORD)
    result = app.test_cli_runner().invoke(args=['create-admin', '--email', 'auto@example.com', '--name', 'Auto'])
    assert result.exit_code == 0 and User.query.filter_by(email='auto@example.com', is_admin=True).count() == 1
    monkeypatch.setenv('AGRINVEST_ADMIN_PASSWORD', 'faible')
    refused = app.test_cli_runner().invoke(args=['create-admin', '--email', 'auto2@example.com', '--name', 'A'])
    assert refused.exit_code != 0 and User.query.filter_by(email='auto2@example.com').count() == 0


# ===================================================================== Sentry (facultatif)
def sentry_app(**config):
    from flask import Flask
    app = Flask('sentry-test')
    app.config.update(SENTRY_ENVIRONMENT='production', SENTRY_TRACES_SAMPLE_RATE=0.1, **config)
    return app


def test_sentry_is_initialised_without_personal_data(monkeypatch):
    import types
    from app import _init_sentry
    calls = []
    monkeypatch.setitem(sys.modules, 'sentry_sdk', types.SimpleNamespace(init=lambda **kw: calls.append(kw)))
    _init_sentry(sentry_app(SENTRY_DSN='https://key@sentry.example/1'))
    assert len(calls) == 1
    assert calls[0]['dsn'] == 'https://key@sentry.example/1' and calls[0]['send_default_pii'] is False
    assert calls[0]['environment'] == 'production' and calls[0]['traces_sample_rate'] == 0.1


def test_sentry_is_skipped_without_dsn_or_under_test(monkeypatch):
    import types
    from app import _init_sentry
    calls = []
    monkeypatch.setitem(sys.modules, 'sentry_sdk', types.SimpleNamespace(init=lambda **kw: calls.append(kw)))
    _init_sentry(sentry_app(SENTRY_DSN=''))
    testing = sentry_app(SENTRY_DSN='https://key@sentry.example/1')
    testing.testing = True
    _init_sentry(testing)
    assert calls == []


def test_missing_sentry_library_only_warns(monkeypatch, caplog):
    from app import _init_sentry
    monkeypatch.setitem(sys.modules, 'sentry_sdk', None)  # import impossible
    app = sentry_app(SENTRY_DSN='https://key@sentry.example/1')
    _init_sentry(app)  # ne plante pas l'application
    assert any('sentry-sdk' in record.getMessage() for record in caplog.records)
