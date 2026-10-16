import pytest

from app.extensions import db
from app.models import User
from app.models.enums import UserRole
from app.services.auth_service import AuthService
from tests.conftest import make_user

PASSWORD = 'Passw0rd!x'


# ---------------------------------------------------------------- inscription
@pytest.mark.parametrize('requested,expected', [
    ('farmer', UserRole.FARMER), ('investor', UserRole.INVESTOR),
    ('admin', UserRole.INVESTOR), ('agent', UserRole.INVESTOR), ('', UserRole.INVESTOR)])
def test_web_register_role_allowlist(client, requested, expected):
    client.post('/register', data={
        'name': 'New User', 'email': 'new@example.com', 'password': PASSWORD,
        'confirm_password': PASSWORD, 'role': requested})
    user = User.query.filter_by(email='new@example.com').one()
    assert user.role == expected
    assert user.is_admin is False


@pytest.mark.parametrize('requested,expected', [
    ('farmer', UserRole.FARMER), ('admin', UserRole.INVESTOR)])
def test_api_register_role_allowlist(client, requested, expected):
    resp = client.post('/api/v1/auth/register', json={
        'name': 'New User', 'email': 'api@example.com', 'password': PASSWORD, 'role': requested})
    assert resp.status_code == 201
    assert User.query.filter_by(email='api@example.com').one().role == expected


def test_register_rejects_weak_password_and_duplicate_email(client, investor):
    client.post('/register', data={'name': 'X', 'email': 'weak@example.com', 'password': 'abc',
                                   'confirm_password': 'abc'})
    assert User.query.filter_by(email='weak@example.com').first() is None
    client.post('/register', data={'name': 'X', 'email': investor.email, 'password': PASSWORD,
                                   'confirm_password': PASSWORD})
    assert User.query.filter_by(email=investor.email).count() == 1


# ----------------------------------------------------------------- connexion
def test_web_login_success_and_failure(client, investor):
    bad = client.post('/login', data={'email': investor.email, 'password': 'wrong'})
    assert bad.status_code == 200  # reste sur la page de connexion
    with client.session_transaction() as sess:
        assert '_user_id' not in sess
    ok = client.post('/login', data={'email': investor.email, 'password': PASSWORD})
    assert ok.status_code == 302
    with client.session_transaction() as sess:
        assert sess['_user_id'] == str(investor.id)


def test_inactive_account_cannot_log_in(client, investor):
    investor.is_active = False
    db.session.commit()
    client.post('/login', data={'email': investor.email, 'password': PASSWORD})
    with client.session_transaction() as sess:
        assert '_user_id' not in sess
    resp = client.post('/api/v1/auth/login', json={'email': investor.email, 'password': PASSWORD})
    assert resp.status_code == 401


@pytest.mark.parametrize('target,allowed', [
    ('/dashboard/investor', True), ('//evil.example/x', False),
    ('https://evil.example/x', False), ('javascript:alert(1)', False)])
def test_login_redirect_is_not_open(client, investor, target, allowed):
    resp = client.post('/login', data={'email': investor.email, 'password': PASSWORD, 'next': target})
    location = resp.headers['Location']
    assert 'evil.example' not in location and 'javascript' not in location
    if allowed:
        assert location.endswith(target)


def test_api_login(client, investor):
    assert client.post('/api/v1/auth/login', json={'email': investor.email, 'password': 'no'}).status_code == 401
    assert client.post('/api/v1/auth/login', json={'email': investor.email}).status_code == 400
    ok = client.post('/api/v1/auth/login', json={'email': investor.email, 'password': PASSWORD})
    assert ok.status_code == 200
    assert 'password_hash' not in ok.get_data(as_text=True)


def test_logout_requires_login(client):
    resp = client.get('/logout')
    assert resp.status_code == 302 and 'login' in resp.headers['Location']


# --------------------------------------------------------- réinitialisation
@pytest.fixture()
def sent_tokens(monkeypatch):
    sent = []
    monkeypatch.setattr('app.services.email_service.EmailService.send_password_reset_email',
                        staticmethod(lambda user, token: sent.append(token)))
    return sent


def test_reset_token_is_single_use(investor):
    token = AuthService.generate_reset_token(investor.email)
    assert AuthService.reset_password(token, 'NewPassw0rd!x') is True
    assert db.session.get(User, investor.id).check_password('NewPassw0rd!x')
    assert AuthService.reset_password(token, 'Another1Pass!') is False  # lien déjà consommé
    assert db.session.get(User, investor.id).check_password('NewPassw0rd!x')


def test_reset_token_rejects_garbage_expired_weak_and_foreign_salt(investor):
    assert AuthService.verify_reset_token('garbage') is None
    token = AuthService.generate_reset_token(investor.email)
    assert AuthService.verify_reset_token(token, expiration=-1) is None
    assert AuthService.reset_password(token, 'short') is False
    email_token = AuthService.generate_email_token(investor.email)
    assert AuthService.verify_reset_token(email_token) is None  # sels distincts


def test_forgot_password_does_not_reveal_accounts(client, investor, sent_tokens):
    known = client.post('/forgot-password', data={'email': investor.email})
    unknown = client.post('/forgot-password', data={'email': 'nobody@example.com'})
    assert known.status_code == unknown.status_code == 302
    assert len(sent_tokens) == 1  # un seul envoi, pour le compte existant


def test_api_reset_flow(client, investor, sent_tokens):
    assert client.post('/api/v1/auth/password/reset-request', json={'email': investor.email}).status_code == 200
    assert client.post('/api/v1/auth/password/reset-request', json={'email': 'nobody@example.com'}).status_code == 200
    assert len(sent_tokens) == 1
    token = sent_tokens[0]
    resp = client.post('/api/v1/auth/password/reset', json={'token': token, 'new_password': 'NewPassw0rd!x'})
    assert resp.status_code == 200
    again = client.post('/api/v1/auth/password/reset', json={'token': token, 'new_password': 'Third1Pass!x'})
    assert again.status_code == 400
    bad = client.post('/api/v1/auth/password/reset', json={'token': 'bad', 'new_password': 'NewPassw0rd!x'})
    assert bad.status_code == 400
    assert client.post('/api/v1/auth/password/reset', json={}).status_code == 400


def test_api_verify_email(client, investor):
    token = AuthService.generate_email_token(investor.email)
    assert client.get(f'/api/v1/auth/verify-email/{token}').status_code == 200
    assert db.session.get(User, investor.id).is_verified is True
    assert client.get('/api/v1/auth/verify-email/garbage').status_code == 400


# ------------------------------------------------------- limitation de débit
# Ces tests n'utilisent pas la fixture `investor` : elle serait créée dans l'application
# standard (limiteur désactivé), pas dans `limited_app` que le client interroge.
def test_login_is_throttled_per_account(limited_app):
    user = make_user('victim@example.com')
    client = limited_app.test_client()
    codes = [client.post('/login', data={'email': user.email, 'password': 'wrong'}).status_code
             for _ in range(12)]
    assert codes[:10] == [200] * 10
    assert codes[10] == 429  # 11e tentative sur le même compte dans l'heure
    # même avec le bon mot de passe, le compte visé reste verrouillé jusqu'à la fin de la fenêtre
    assert client.post('/login', data={'email': user.email, 'password': PASSWORD}).status_code == 429


def test_login_throttle_is_per_account_not_global(limited_app):
    victim = make_user('victim@example.com')
    other = make_user('someone@example.com')
    client = limited_app.test_client()
    for _ in range(10):
        client.post('/login', data={'email': victim.email, 'password': 'wrong'})
    assert client.post('/login', data={'email': other.email, 'password': PASSWORD}).status_code == 302


def test_api_login_is_throttled_per_ip(limited_app):
    client = limited_app.test_client()
    codes = [client.post('/api/v1/auth/login', json={'email': f'x{i}@example.com', 'password': 'p'}).status_code
             for i in range(22)]
    assert 429 in codes  # 20 par heure et par IP
    assert client.post('/api/v1/auth/login', json={'email': 'y@example.com', 'password': 'p'}).get_json()['code'] == 429
