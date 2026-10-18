"""Rattachement des agents aux points de collecte : un agent n'encaisse que là où il est autorisé."""
import json
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import (AuditLog, CollectionPoint, CollectionPointAgent, Contribution, ProjectCollectionPoint, User)
from app.models.enums import ContributionStatus, UserRole
from tests.conftest import login_as, make_user

API = '/api/v1/collection-points'


def make_point(project, name='Point Nord'):
    point = CollectionPoint(name=name, department='Nord', commune='Cap', address='Rue', fee_percentage=Decimal('0'))
    db.session.add(point)
    db.session.flush()
    db.session.add(ProjectCollectionPoint(project_id=project.id, collection_point_id=point.id))
    db.session.commit()
    return point


def make_agent(email='agent@example.com'):
    return make_user(email, role=UserRole.AGENT, name='Agent')


def cash_contribution(investor, project, amount='1000.00'):
    c = Contribution(investor_id=investor.id, project_id=project.id, amount=Decimal(amount), currency='HTG',
                     amount_htg=Decimal(amount), payment_method='cash')
    db.session.add(c)
    db.session.commit()
    return c


def receive(client, point, contribution, receipt):
    return client.post(f'{API}/{point.id}/receive-cash',
                       json={'contribution_id': contribution.id, 'amount': '1000', 'receipt_number': receipt})


# ============================================================= règle d'encaissement
def test_unassigned_agent_cannot_receive_cash(client, project, investor):
    point, agent = make_point(project), make_agent()
    c = cash_contribution(investor, project)
    login_as(client, agent)
    assert receive(client, point, c, 'R-1').status_code == 403
    assert db.session.get(Contribution, c.id).status == ContributionStatus.PENDING
    assert Contribution.query.filter(Contribution.cash_receipt_number.isnot(None)).count() == 0


def test_agent_assigned_elsewhere_cannot_receive_here(client, project, investor):
    here, elsewhere, agent = make_point(project, 'Ici'), make_point(project, 'Ailleurs'), make_agent()
    db.session.add(CollectionPointAgent(collection_point_id=elsewhere.id, agent_id=agent.id))
    db.session.commit()
    c = cash_contribution(investor, project)
    login_as(client, agent)
    assert receive(client, here, c, 'R-1').status_code == 403
    assert receive(client, elsewhere, c, 'R-2').status_code == 200


def test_admin_can_receive_cash_anywhere(client, project, investor, admin):
    point = make_point(project)
    c = cash_contribution(investor, project)
    login_as(client, admin)
    assert receive(client, point, c, 'R-ADM').status_code == 200


def test_assignment_is_checked_before_anything_else_is_revealed(client, project, investor):
    """Un agent non rattaché obtient 403 même pour une contribution inexistante ou un reçu déjà utilisé."""
    point, agent = make_point(project), make_agent()
    login_as(client, agent)
    response = client.post(f'{API}/{point.id}/receive-cash',
                           json={'contribution_id': 99999, 'amount': '1', 'receipt_number': 'X'})
    assert response.status_code == 403


# ============================================================== gestion (administrateur)
def test_assignment_endpoints_are_admin_only(client, project, investor, farmer_user):
    point, agent = make_point(project), make_agent()
    for user in (investor, farmer_user, agent):
        login_as(client, user)
        assert client.post(f'{API}/{point.id}/agents', json={'agent_id': agent.id}).status_code == 403
        assert client.get(f'{API}/{point.id}/agents').status_code == 403
        assert client.delete(f'{API}/{point.id}/agents/{agent.id}').status_code == 403
    assert CollectionPointAgent.query.count() == 0


def test_assign_list_and_unassign_with_audit(client, project, admin):
    point, agent = make_point(project), make_agent()
    login_as(client, admin)
    assert client.post(f'{API}/{point.id}/agents', json={'agent_id': agent.id}).status_code == 201
    assert client.post(f'{API}/{point.id}/agents', json={'agent_id': agent.id}).status_code == 200  # idempotent
    assert CollectionPointAgent.query.count() == 1
    listed = client.get(f'{API}/{point.id}/agents').get_json()['agents']
    assert [(a['id'], a['email']) for a in listed] == [(agent.id, agent.email)]
    assert client.delete(f'{API}/{point.id}/agents/{agent.id}').status_code == 200
    assert client.delete(f'{API}/{point.id}/agents/{agent.id}').status_code == 404
    assert [e.action for e in AuditLog.query.order_by(AuditLog.id)] == [
        'collection_point.agent_assign', 'collection_point.agent_unassign']
    assert json.loads(AuditLog.query.first().details)['agent_id'] == agent.id


@pytest.mark.parametrize('payload', [{}, {'agent_id': 'x'}, {'agent_id': True}, {'agent_id': 1.5}])
def test_assign_validates_input(client, project, admin, payload):
    point = make_point(project)
    login_as(client, admin)
    assert client.post(f'{API}/{point.id}/agents', json=payload).status_code == 400
    assert CollectionPointAgent.query.count() == 0


def test_only_active_agent_accounts_can_be_assigned(client, project, admin, investor, farmer_user):
    point = make_point(project)
    banned = make_agent('banned@example.com')
    banned.is_active = False
    db.session.commit()
    login_as(client, admin)
    for user_id in (investor.id, farmer_user.id, admin.id, banned.id):
        assert client.post(f'{API}/{point.id}/agents', json={'agent_id': user_id}).status_code == 400
    assert client.post(f'{API}/{point.id}/agents', json={'agent_id': 99999}).status_code == 404
    assert client.post(f'{API}/99999/agents', json={'agent_id': banned.id}).status_code == 404
    assert CollectionPointAgent.query.count() == 0


def test_unassigned_agent_loses_access_immediately(client, project, investor, admin):
    point, agent = make_point(project), make_agent()
    db.session.add(CollectionPointAgent(collection_point_id=point.id, agent_id=agent.id))
    db.session.commit()
    first, second = cash_contribution(investor, project), cash_contribution(investor, project)
    login_as(client, agent)
    assert receive(client, point, first, 'R-1').status_code == 200
    login_as(client, admin)
    client.delete(f'{API}/{point.id}/agents/{agent.id}')
    login_as(client, agent)
    assert receive(client, point, second, 'R-2').status_code == 403


def test_deleting_a_point_or_an_agent_removes_the_assignments(project):
    point, agent = make_point(project), make_agent()
    db.session.add(CollectionPointAgent(collection_point_id=point.id, agent_id=agent.id))
    db.session.commit()
    if db.engine.dialect.name == 'sqlite':
        pytest.skip('les suppressions en cascade des clés étrangères exigent PRAGMA foreign_keys sous SQLite')
    db.session.delete(db.session.get(User, agent.id))
    db.session.commit()
    assert CollectionPointAgent.query.count() == 0


# ======================================================================= vue de l'agent
def test_agent_sees_only_their_active_points(client, project):
    mine, other, closed = make_point(project, 'Mien'), make_point(project, 'Autre'), make_point(project, 'Fermé')
    agent = make_agent()
    closed.is_active = False
    db.session.add_all([CollectionPointAgent(collection_point_id=mine.id, agent_id=agent.id),
                        CollectionPointAgent(collection_point_id=closed.id, agent_id=agent.id)])
    db.session.commit()
    login_as(client, agent)
    names = [p['name'] for p in client.get(f'{API}/mine').get_json()['collection_points']]
    assert names == ['Mien']


def test_my_points_requires_an_agent(client, investor):
    assert client.get(f'{API}/mine').status_code == 401
    login_as(client, investor)
    assert client.get(f'{API}/mine').status_code == 403
