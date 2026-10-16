from decimal import Decimal

import pytest

from app.extensions import db
from app.models import Contribution, Project
from tests.conftest import login_as

ADMIN_ENDPOINTS = [('get', '/api/v1/admin/stats'), ('get', '/api/v1/admin/users'),
                   ('get', '/api/v1/admin/projects/pending'), ('get', '/api/v1/admin/dashboard'),
                   ('post', '/api/v1/admin/users/1/ban'), ('post', '/api/v1/admin/projects/1/approve')]


@pytest.mark.parametrize('method,url', ADMIN_ENDPOINTS)
def test_admin_api_rejects_anonymous_and_non_admins(client, investor, farmer_user, method, url):
    assert getattr(client, method)(url).status_code == 401
    for user in (investor, farmer_user):
        login_as(client, user)
        assert getattr(client, method)(url).status_code == 403


def test_admin_api_allows_admin(client, admin):
    login_as(client, admin)
    assert client.get('/api/v1/admin/users').status_code == 200


def test_admin_web_pages_require_admin(client, investor, admin):
    anonymous = client.get('/admin/users')
    assert anonymous.status_code in (302, 401, 403)
    login_as(client, investor)
    assert client.get('/admin/users').status_code in (302, 401, 403)
    login_as(client, admin)
    assert client.get('/admin/users').status_code == 200


@pytest.fixture()
def contribution(investor, project):
    c = Contribution(investor_id=investor.id, project_id=project.id, amount=Decimal('500'),
                     currency='HTG', amount_htg=Decimal('500'), payment_method='cash')
    db.session.add(c)
    db.session.commit()
    return c


def test_contribution_is_private(client, contribution, other_investor, investor, admin):
    url = f'/api/v1/contributions/{contribution.id}'
    assert client.get(url).status_code == 401
    login_as(client, other_investor)
    assert client.get(url).status_code == 403
    login_as(client, investor)
    assert client.get(url).status_code == 200
    login_as(client, admin)
    assert client.get(url).status_code == 200


def test_only_project_owner_or_admin_can_refund(client, contribution, other_investor, investor):
    url = f'/api/v1/contributions/{contribution.id}/refund'
    for user in (other_investor, investor):  # même l'investisseur ne rembourse pas lui-même
        login_as(client, user)
        assert client.post(url).status_code == 403


def test_contract_download_is_private(client, contribution, other_investor):
    login_as(client, other_investor)
    assert client.get(f'/contribution/{contribution.id}/contract').status_code == 403


def test_confirm_requires_ownership(client, contribution, other_investor):
    login_as(client, other_investor)
    resp = client.post(f'/api/v1/contributions/{contribution.id}/confirm', json={'payment_intent_id': 'x'})
    assert resp.status_code == 403


def test_project_modification_requires_owner(client, project, other_investor, farmer_user):
    for url in (f'/project/{project.id}/edit', f'/project/{project.id}/publish',
                f'/project/{project.id}/delete'):
        login_as(client, other_investor)
        assert client.post(url).status_code in (302, 401, 403)
        login_as(client, farmer_user)  # agriculteur, mais pas propriétaire
        assert client.post(url).status_code in (302, 403, 404)
    assert db.session.get(Project, project.id) is not None


def test_investing_requires_investor_role(client, project, farmer_user):
    login_as(client, farmer_user)
    resp = client.post(f'/invest/{project.id}', data={'amount': '500', 'payment_method': 'cash'})
    assert resp.status_code in (302, 403)
    assert Contribution.query.count() == 0


def test_my_contributions_lists_only_own(client, contribution, other_investor, investor):
    login_as(client, other_investor)
    assert client.get('/api/v1/contributions/my-contributions').get_json()['contributions'] == []
    login_as(client, investor)
    assert len(client.get('/api/v1/contributions/my-contributions').get_json()['contributions']) == 1
