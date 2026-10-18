import re

import pytest

from app.extensions import db, mail
from app.models import User
from app.services.email_service import EmailService, _html_to_text
from tests.conftest import login_as

PASSWORD = 'Passw0rd!x'


def links(message):
    return re.findall(r'https?://[^\s")<]+', message.html)


def register(client, **extra):
    return client.post('/register', data={
        'name': 'New User', 'email': 'new@example.com', 'password': PASSWORD,
        'confirm_password': PASSWORD, **extra})


# ------------------------------------------------------------- vérification
def test_web_registration_sends_welcome_with_verification_link(client, app):
    with mail.record_messages() as outbox:
        register(client)
    assert len(outbox) == 1
    message = outbox[0]
    assert message.recipients == ['new@example.com']
    link = next(l for l in links(message) if '/verify-email/' in l)
    assert link.startswith(app.config['BASE_URL'])
    assert '(' in message.body and '/verify-email/' in message.body  # version texte avec le lien
    assert '<' not in message.body


def test_verification_link_marks_user_verified(client, app):
    with mail.record_messages() as outbox:
        register(client)
    path = re.search(r'/verify-email/[^\s")<]+', outbox[0].html).group(0)
    client.get('/logout')
    assert User.query.filter_by(email='new@example.com').one().is_verified is False
    assert client.get(path).status_code == 302
    assert User.query.filter_by(email='new@example.com').one().is_verified is True


def test_invalid_verification_link_changes_nothing(client, investor):
    resp = client.get('/verify-email/garbage')
    assert resp.status_code == 302 and 'login' in resp.headers['Location']
    assert db.session.get(User, investor.id).is_verified is not True


def test_api_registration_sends_welcome(client):
    with mail.record_messages() as outbox:
        resp = client.post('/api/v1/auth/register', json={
            'name': 'Api User', 'email': 'api@example.com', 'password': PASSWORD})
    assert resp.status_code == 201
    assert [m.recipients for m in outbox] == [['api@example.com']]


def test_resend_verification(client, investor):
    assert client.post('/api/v1/auth/resend-verification').status_code == 401
    login_as(client, investor)
    with mail.record_messages() as outbox:
        assert client.post('/api/v1/auth/resend-verification').status_code == 200
    assert len(outbox) == 1 and '/verify-email/' in outbox[0].html
    investor.is_verified = True
    db.session.commit()
    with mail.record_messages() as outbox:
        assert client.post('/api/v1/auth/resend-verification').status_code == 200
    assert outbox == []  # déjà vérifié : rien n'est envoyé


# ------------------------------------------------- réinitialisation du mot de passe
def test_reset_email_is_sent_and_link_works_end_to_end(client, investor):
    with mail.record_messages() as outbox:
        client.post('/forgot-password', data={'email': investor.email})
    assert len(outbox) == 1
    path = re.search(r'/reset-password/[^\s")<]+', outbox[0].html).group(0)
    resp = client.post(path, data={'password': 'NewPassw0rd!x', 'confirm_password': 'NewPassw0rd!x'})
    assert resp.status_code == 302
    assert db.session.get(User, investor.id).check_password('NewPassw0rd!x')


def test_forgot_password_unknown_address_sends_nothing(client):
    with mail.record_messages() as outbox:
        resp = client.post('/forgot-password', data={'email': 'nobody@example.com'})
    assert resp.status_code == 302 and outbox == []


def test_reset_link_ignores_forged_host_header(client, investor):
    """Un attaquant ne doit pas pouvoir faire pointer le lien vers son propre domaine."""
    with mail.record_messages() as outbox:
        client.post('/forgot-password', data={'email': investor.email}, headers={'Host': 'evil.example'})
    assert outbox and 'evil.example' not in outbox[0].html + outbox[0].body


def test_email_failure_does_not_crash_forgot_password(client, investor, monkeypatch):
    monkeypatch.setattr(mail, 'send', lambda msg: (_ for _ in ()).throw(RuntimeError('smtp down')))
    resp = client.post('/forgot-password', data={'email': investor.email})
    assert resp.status_code == 302


# ----------------------------------------------------------------- contact
def test_contact_form_sends_message_to_team(client, app):
    with mail.record_messages() as outbox:
        client.post('/contact', data={'name': 'Jean', 'email': 'jean@example.com',
                                      'subject': 'Question', 'message': 'Bonjour'})
    assert len(outbox) == 1
    assert outbox[0].reply_to == 'jean@example.com'
    assert 'Bonjour' in outbox[0].body and outbox[0].subject == '[Contact] Question'


def test_contact_form_blocks_header_injection(client):
    with mail.record_messages() as outbox:
        client.post('/contact', data={'name': 'X', 'email': 'x@example.com',
                                      'subject': 'Hi\r\nBcc: victim@example.com', 'message': 'm'})
    assert len(outbox) == 1
    assert '\n' not in outbox[0].subject and '\r' not in outbox[0].subject
    assert 'victim@example.com' not in outbox[0].send_to


def test_contact_form_requires_fields_and_reports_failure(client, monkeypatch):
    with mail.record_messages() as outbox:
        client.post('/contact', data={'name': '', 'email': '', 'message': ''})
    assert outbox == []
    monkeypatch.setattr(mail, 'send', lambda msg: (_ for _ in ()).throw(RuntimeError('smtp down')))
    resp = client.post('/contact', data={'name': 'J', 'email': 'j@example.com', 'message': 'm'},
                       follow_redirects=True)
    assert 'Une erreur est survenue' in resp.get_data(as_text=True)


# ------------------------------------------------------------------ divers
def test_every_email_template_exists(app):
    for name in ('welcome', 'verify_email', 'password_reset', 'project_funded', 'project_update',
                 'contribution_confirmation'):
        app.jinja_env.get_template(f'email/{name}.html')


def test_html_to_text_keeps_links_and_drops_markup():
    text = _html_to_text('<style>p{}</style><p>Salut <b>toi</b></p><a href="https://x.test/a">Lien</a>')
    assert 'Lien (https://x.test/a)' in text and '<' not in text and 'p{}' not in text
