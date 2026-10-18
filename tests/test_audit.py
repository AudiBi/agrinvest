"""Journal d'audit : chaque action sensible laisse une trace, validée avec l'action elle-même."""
import json
from datetime import timedelta
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import (AuditLog, CollectionPoint, Contribution, Project, ProjectCollectionPoint, User)
from app.models.contribution import utc_now
from app.models.enums import ContributionStatus, ProjectStatus, UserRole
from tests.conftest import login_as, make_user

API = '/api/v1'


def logs(action=None):
    query = AuditLog.query
    if action:
        query = query.filter_by(action=action)
    return query.order_by(AuditLog.id).all()


def one(action):
    entries = logs(action)
    assert len(entries) == 1, f'{action}: {[e.action for e in logs()]}'
    return entries[0]


def details(entry):
    return json.loads(entry.details) if entry.details else {}


@pytest.fixture()
def admin_client(client, admin):
    return login_as(client, admin)


def completed_contribution(investor, project, amount='1000.00', method='cash'):
    c = Contribution(investor_id=investor.id, project_id=project.id, amount=Decimal(amount), currency='HTG',
                     amount_htg=Decimal(amount), payment_method=method)
    db.session.add(c)
    db.session.commit()
    c.mark_completed()
    return c


# ======================================================================= comptes
def test_user_moderation_is_traced_with_actor_target_and_ip(admin_client, admin, investor):
    for url, action in ((f'verify', 'user.verify'), ('ban', 'user.ban'), ('unban', 'user.unban')):
        assert admin_client.post(f'{API}/admin/users/{investor.id}/{url}').status_code == 200
        entry = one(action)
        assert (entry.actor_id, entry.actor_email, entry.target_type, entry.target_id) == (
            admin.id, admin.email, 'users', investor.id)
        assert entry.ip_address and entry.created_at


def test_failed_actions_leave_no_trace(admin_client, admin):
    assert admin_client.post(f'{API}/admin/users/{admin.id}/ban').status_code == 400  # ne peut pas se bannir
    assert admin_client.post(f'{API}/admin/users/9999/ban').status_code == 404
    assert logs() == []


def test_role_changes_are_traced_only_when_the_role_changes(admin_client, investor):
    url = f'{API}/users/{investor.id}'
    admin_client.put(url, json={'role': 'investor', 'name': 'Même rôle'})
    assert logs('user.role_change') == []
    admin_client.put(url, json={'role': 'farmer'})
    assert details(one('user.role_change')) == {'old': 'investor', 'new': 'farmer'}


def test_ambassador_grant_and_deactivation_are_traced(admin_client, admin):
    candidate = make_user('dia@example.com', country='US')
    admin_client.post(f'{API}/admin/users/{candidate.id}/approve-ambassador')
    assert details(one('user.role_change')) == {'old': 'investor', 'new': 'ambassador'}
    admin_client.delete(f'{API}/users/{candidate.id}')
    assert one('user.deactivate').target_id == candidate.id


# ====================================================================== projets
def test_project_moderation_is_traced(admin_client, project, farmer_user):
    pending = Project(title='En attente', slug='attente', description='d', amount_needed=Decimal('1000'),
                      farmer_id=farmer_user.id, status=ProjectStatus.PENDING, is_published=False,
                      min_investment=Decimal('10'), currency='HTG')
    db.session.add(pending)
    db.session.commit()
    admin_client.post(f'{API}/admin/projects/{pending.id}/reject', json={'reason': 'Photos floues'})
    assert details(one('project.reject')) == {'reason': 'Photos floues'}
    pending.status = ProjectStatus.PENDING
    db.session.commit()
    admin_client.post(f'{API}/admin/projects/{pending.id}/approve')
    assert one('project.approve').target_id == pending.id


def test_admin_financial_edits_record_before_and_after_but_farmer_edits_do_not(client, project, admin):
    owner = db.session.get(User, project.farmer_id)
    login_as(client, owner)
    client.put(f'{API}/projects/{project.id}', json={'title': 'Nouveau titre'})
    assert logs() == []
    login_as(client, admin)
    client.put(f'{API}/projects/{project.id}', json={'min_investment': 25})
    changes = details(one('project.update_financial'))['changes']
    assert changes == {'min_investment': ['100.00', '25']} or changes['min_investment'][1] == '25'


def test_unpublish_and_feature_are_traced(admin_client, project):
    admin_client.post(f'{API}/projects/{project.id}/feature')
    admin_client.post(f'{API}/projects/{project.id}/unfeature')
    admin_client.post(f'{API}/projects/{project.id}/unpublish')
    assert [e.action for e in logs()] == ['project.feature', 'project.unfeature', 'project.unpublish']
    assert details(logs('project.unpublish')[0])['previous_status'] == 'published'


# ================================================================== argent
def test_payout_lifecycle_is_traced_without_account_numbers(admin_client, investor, project):
    completed_contribution(investor, project)
    resp = admin_client.post(f'{API}/commission/payouts', json={
        'payout_method': 'bank_transfer', 'payout_account': 'FR76-SECRET-IBAN', 'transfer_fee': 2})
    assert resp.status_code == 201
    created = one('payout.create')
    assert 'SECRET' not in created.details and 'payout_account' not in created.details
    assert details(created)['transfer_fee'] == '2'
    payout_id = resp.get_json()['payout']['id']
    admin_client.post(f'{API}/commission/payouts/{payout_id}/complete')
    assert one('payout.complete').target_id == payout_id


def test_rejected_payout_leaves_no_trace(admin_client, investor, project):
    completed_contribution(investor, project)
    assert admin_client.post(f'{API}/commission/payouts', json={'transfer_fee': 10 ** 6}).status_code == 400
    assert admin_client.post(f'{API}/commission/payouts', json={'transfer_fee': -1}).status_code == 400
    assert logs() == []


def test_transfer_batches_are_traced(admin_client, investor, project):
    c = completed_contribution(investor, project)
    body = {'contribution_ids': [c.id], 'destination_bank': 'Unibank', 'destination_account': 'ACC-999',
            'beneficiary_name': 'AgriInvest'}
    admin_client.post(f'{API}/transfers/batches', json=body)
    created = one('transfer.create')
    assert 'ACC-999' not in created.details  # numéro de compte jamais journalisé
    transfer_id = db.session.execute(db.text('select id from fund_transfers')).scalar()
    admin_client.put(f'{API}/transfers/batches/{transfer_id}/status', json={'status': 'processing'})
    assert details(one('transfer.status'))['old'] == 'pending'


def test_refunds_are_traced(admin_client, investor, project, monkeypatch):
    c = completed_contribution(investor, project, method='stripe')
    monkeypatch.setattr('app.utils.payments.process_refund', lambda contribution: True)
    assert admin_client.post(f'{API}/contributions/{c.id}/refund').status_code == 200
    entry = one('contribution.refund')
    assert (entry.target_id, details(entry)['payment_method']) == (c.id, 'stripe')


def test_failed_refund_leaves_no_trace(admin_client, investor, project, monkeypatch):
    c = completed_contribution(investor, project, method='stripe')
    monkeypatch.setattr('app.utils.payments.process_refund', lambda contribution: False)
    assert admin_client.post(f'{API}/contributions/{c.id}/refund').status_code == 400
    assert logs() == [] and db.session.get(Contribution, c.id).status == ContributionStatus.COMPLETED


def test_cash_receipts_identify_the_agent(client, project, investor):
    agent = make_user('agent@example.com', role=UserRole.AGENT)
    point = CollectionPoint(name='P', department='N', commune='C', address='A', fee_percentage=Decimal('2'))
    db.session.add(point)
    db.session.flush()
    db.session.add(ProjectCollectionPoint(project_id=project.id, collection_point_id=point.id))
    c = Contribution(investor_id=investor.id, project_id=project.id, amount=Decimal('1000'), currency='HTG',
                     amount_htg=Decimal('1000'), payment_method='cash')
    db.session.add(c)
    db.session.commit()
    login_as(client, agent)
    client.post(f'{API}/collection-points/{point.id}/receive-cash',
                json={'contribution_id': c.id, 'amount': '1000', 'receipt_number': 'R-77'})
    entry = one('cash.receive')
    assert (entry.actor_id, entry.target_id) == (agent.id, c.id)
    assert details(entry)['receipt'] == 'R-77' and details(entry)['point_id'] == point.id


def test_collection_point_changes_are_traced(admin_client):
    created = admin_client.post(f'{API}/collection-points', json={
        'name': 'P', 'department': 'N', 'commune': 'C', 'address': 'A', 'fee_percentage': 1})
    point_id = created.get_json()['collection_point']['id']
    assert one('collection_point.create').target_id == point_id
    admin_client.put(f'{API}/collection-points/{point_id}', json={'fee_percentage': 5, 'name': 'P'})
    changes = details(one('collection_point.update'))['changes']
    assert list(changes) == ['fee_percentage']  # le nom, inchangé, n'apparaît pas


def test_weather_alerts_are_traced(admin_client):
    now = utc_now()
    admin_client.post(f'{API}/weather/alerts', json={
        'zone': 'Nord', 'alert_type': 'rain', 'severity': 'critical', 'message_ht': 'x',
        'starts_at': (now - timedelta(hours=1)).isoformat(), 'ends_at': (now + timedelta(hours=1)).isoformat()})
    assert details(one('weather.alert.create')) == {'zone': 'Nord', 'severity': 'critical'}


# ============================================================ administration web
def test_web_admin_actions_are_traced(client, admin, project, farmer_user):
    login_as(client, admin)
    target = make_user('cible@example.com')
    client.post(f'/admin/users/{target.id}/toggle-active')
    client.post(f'/admin/users/{target.id}/toggle-active')
    client.post(f'/admin/users/{target.id}/toggle-verified')
    client.post(f'/admin/users/{target.id}/make-admin')
    client.post(f'/admin/users/{target.id}/make-admin')
    assert [e.action for e in logs()] == ['user.deactivate', 'user.activate', 'user.verify',
                                          'user.admin_granted', 'user.admin_revoked']
    client.post(f'/admin/users/{target.id}/delete')
    assert details(one('user.delete'))['previous_email'] == 'cible@example.com'
    client.post(f'/admin/projects/{project.id}/feature')
    assert one('project.feature').target_id == project.id


def test_web_project_approval_and_rejection_are_traced(client, admin, farmer_user):
    login_as(client, admin)
    for slug, action_url, action in (('a', 'approve', 'project.approve'), ('b', 'reject', 'project.reject')):
        p = Project(title=slug, slug=slug, description='d', amount_needed=Decimal('1000'), farmer_id=farmer_user.id,
                    status=ProjectStatus.PENDING, is_published=False, min_investment=Decimal('10'), currency='HTG')
        db.session.add(p)
        db.session.commit()
        client.post(f'/admin/projects/{p.id}/{action_url}', data={'reason': 'non conforme'})
        assert one(action).target_id == p.id
    approved = db.session.execute(db.text("select published_at from projects where slug='a'")).scalar()
    assert approved is not None


def test_web_cannot_delete_a_project_with_collected_funds(client, admin, project):
    login_as(client, admin)
    project.amount_raised = Decimal('500')
    db.session.commit()
    client.post(f'/admin/projects/{project.id}/delete')
    assert db.session.get(Project, project.id).status == ProjectStatus.PUBLISHED  # inchangé
    assert logs() == []
    project.amount_raised = Decimal('0')
    db.session.commit()
    client.post(f'/admin/projects/{project.id}/delete')
    assert db.session.get(Project, project.id).status == ProjectStatus.CANCELLED
    assert one('project.delete')


def test_web_settings_are_validated_then_traced(client, admin, monkeypatch):
    saved = {}
    monkeypatch.setattr('app.utils.config.set_config_value', lambda key, value, config_file=None: saved.update({key: value}))
    login_as(client, admin)
    for bad in ({'commission_rate': '55'}, {'commission_rate': 'abc'}, {'min_contribution': '0'},
                {'min_contribution': '500', 'max_contribution': '100'}, {'max_contribution': 'x'}):
        client.post('/admin/settings', data={'commission_rate': '3', 'min_contribution': '100',
                                             'max_contribution': '1000', **bad})
    assert saved == {} and logs() == []
    client.post('/admin/settings', data={'commission_rate': '4', 'min_contribution': '100', 'max_contribution': '1000'})
    assert saved['COMMISSION_RATE'] == 4.0
    assert details(one('settings.update'))['commission_rate'] == 4.0


# ===================================================================== lecture
def test_audit_log_is_admin_only(client, investor, admin):
    assert client.get(f'{API}/admin/audit-logs').status_code == 401
    login_as(client, investor)
    assert client.get(f'{API}/admin/audit-logs').status_code == 403
    login_as(client, admin)
    assert client.get(f'{API}/admin/audit-logs').status_code == 200


def test_audit_log_filters_ordering_and_limits(admin_client, admin, investor):
    admin_client.post(f'{API}/admin/users/{investor.id}/verify')
    admin_client.post(f'{API}/admin/users/{investor.id}/ban')
    body = admin_client.get(f'{API}/admin/audit-logs').get_json()
    assert [e['action'] for e in body['logs']] == ['user.ban', 'user.verify']  # plus récent d'abord
    assert admin_client.get(f'{API}/admin/audit-logs?action=user.b').get_json()['total'] == 1
    assert admin_client.get(f'{API}/admin/audit-logs?action=%').get_json()['total'] == 0  # joker neutralisé
    assert admin_client.get(f'{API}/admin/audit-logs?action=user').get_json()['total'] == 2
    assert admin_client.get(f'{API}/admin/audit-logs?target_type=users&target_id={investor.id}').get_json()['total'] == 2
    assert admin_client.get(f'{API}/admin/audit-logs?actor_id={admin.id}').get_json()['total'] == 2
    assert admin_client.get(f'{API}/admin/audit-logs?actor_id=9999').get_json()['total'] == 0
    today = utc_now().strftime('%Y-%m-%d')
    assert admin_client.get(f'{API}/admin/audit-logs?since={today}&until={today}').get_json()['total'] == 2
    assert admin_client.get(f'{API}/admin/audit-logs?until=2000-01-01').get_json()['total'] == 0
    assert admin_client.get(f'{API}/admin/audit-logs?since=hier').status_code == 400
    assert admin_client.get(f'{API}/admin/audit-logs?per_page=100000').get_json()['per_page'] == 100


def test_audit_entries_are_not_modifiable_through_the_api(admin_client):
    for method in ('post', 'put', 'delete', 'patch'):
        assert getattr(admin_client, method)(f'{API}/admin/audit-logs').status_code == 405


def test_action_and_trace_roll_back_together(admin_client, investor, monkeypatch):
    def boom():
        raise RuntimeError('base de données indisponible')

    monkeypatch.setattr(db.session, 'commit', boom)
    with pytest.raises(RuntimeError):
        admin_client.post(f'{API}/admin/users/{investor.id}/ban')
    monkeypatch.undo()
    db.session.rollback()
    assert AuditLog.query.count() == 0  # jamais de trace d'une action qui n'a pas eu lieu
    assert db.session.get(User, investor.id).is_active is True
