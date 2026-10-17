"""Commissions, versements au CEO, lots de transfert et administration."""
import json
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import (CommissionAuditLog, Contribution, FundTransfer, PlatformCommissionConfig,
                        PlatformEarning, Project, User)
from app.models.enums import ContributionStatus
from tests.conftest import login_as

COMMISSION = '/api/v1/commission'
TRANSFERS = '/api/v1/transfers'
ADMIN = '/api/v1/admin'


def completed_contribution(investor, project, amount='1000.00'):
    c = Contribution(investor_id=investor.id, project_id=project.id, amount=Decimal(amount), currency='HTG',
                     amount_htg=Decimal(amount), payment_method='cash')
    db.session.add(c)
    db.session.commit()
    c.mark_completed()
    return c


@pytest.fixture()
def admin_client(client, admin):
    return login_as(client, admin)


# ------------------------------------------------------------ configuration
def test_commission_config_requires_admin(client, investor):
    login_as(client, investor)
    assert client.post(f'{COMMISSION}/config', json={'commission_type': 'x', 'percentage': 3}).status_code == 403


def test_create_config_writes_audit_log_atomically(admin_client):
    resp = admin_client.post(f'{COMMISSION}/config', json={
        'commission_type': 'platform_fee', 'percentage': 4, 'is_default': True, 'reason': 'test'})
    assert resp.status_code == 201
    log = CommissionAuditLog.query.one()
    assert (log.action, log.new_percentage, log.reason) == ('create', Decimal('4'), 'test')


@pytest.mark.parametrize('percentage', [25, -1, 'abc', None, 'NaN', 'Infinity'])
def test_config_rejects_invalid_percentage(admin_client, percentage):
    resp = admin_client.post(f'{COMMISSION}/config', json={'commission_type': 'platform_fee', 'percentage': percentage})
    assert resp.status_code == 400
    assert PlatformCommissionConfig.query.count() == 0


def test_config_rejects_missing_type_and_bad_amounts(admin_client):
    assert admin_client.post(f'{COMMISSION}/config', json={'percentage': 3}).status_code == 400
    bad = admin_client.post(f'{COMMISSION}/config', json={
        'commission_type': 'x', 'percentage': 3, 'fixed_fee': 'oops'})
    assert bad.status_code == 400


def test_update_config_logs_old_and_new_and_validates(admin_client):
    created = admin_client.post(f'{COMMISSION}/config', json={'commission_type': 'x', 'percentage': 3}).get_json()
    config_id = created['config']['id']
    assert admin_client.put(f'{COMMISSION}/config/{config_id}', json={'percentage': 99}).status_code == 400
    assert admin_client.put(f'{COMMISSION}/config/{config_id}', json={'percentage': 5}).status_code == 200
    log = CommissionAuditLog.query.filter_by(action='update').one()
    assert (log.old_percentage, log.new_percentage) == (Decimal('3'), Decimal('5'))


def test_listing_survives_an_inactive_default(admin_client):
    admin_client.post(f'{COMMISSION}/config', json={'commission_type': 'x', 'percentage': 3, 'is_default': True})
    config = PlatformCommissionConfig.query.one()
    config.is_active = False
    db.session.commit()
    resp = admin_client.get(f'{COMMISSION}/config')
    assert resp.status_code == 200 and resp.get_json()['default_commission'] == 3.0
    assert admin_client.get(f'{COMMISSION}/dashboard').status_code == 200


def test_category_specific_config_beats_the_default(app, project):
    project.category = 'coffee'
    db.session.commit()
    db.session.add_all([
        PlatformCommissionConfig(commission_type='platform_fee', percentage=Decimal('3'), is_default=True),
        PlatformCommissionConfig(commission_type='platform_fee', percentage=Decimal('5'),
                                 project_category=project.category)])
    db.session.commit()
    assert project.get_commission_config().percentage == Decimal('5')


def test_commission_is_rounded_to_the_cent(app):
    config = PlatformCommissionConfig(percentage=Decimal('3'), commission_type='platform_fee',
                                      min_amount_to_apply=Decimal('0'), fixed_fee=Decimal('0'))
    assert config.calculate_commission(Decimal('16.50')) == Decimal('0.50')   # 0,495 -> 0,50
    assert config.calculate_commission(Decimal('100.05')) == Decimal('3.00')  # 3,0015 -> 3,00


# ------------------------------------------------------------- refunds & payouts
def test_refund_cancels_pending_commission_so_it_is_never_paid(admin_client, investor, project):
    c = completed_contribution(investor, project)
    earning = PlatformEarning.query.filter_by(contribution_id=c.id).one()
    assert earning.status == 'pending'
    c.mark_refunded()
    assert db.session.get(PlatformEarning, earning.id).status == 'cancelled'
    assert admin_client.post(f'{COMMISSION}/payouts', json={}).status_code == 400  # rien à verser
    assert admin_client.get(f'{COMMISSION}/dashboard').get_json()['total_commissions_htg'] == 0


def test_payout_flow_and_double_payment_protection(admin_client, investor, project):
    completed_contribution(investor, project, '1000.00')
    completed_contribution(investor, project, '2000.00')
    resp = admin_client.post(f'{COMMISSION}/payouts', json={'transfer_fee': 5})
    assert resp.status_code == 201
    payout = resp.get_json()['payout']
    assert Decimal(str(payout['payout_amount'])) == Decimal('90.00')  # 3 % de 3000
    assert {e.status for e in PlatformEarning.query.all()} == {'pending_payout'}
    # deuxième demande : plus rien à verser, la même commission n'est jamais versée deux fois
    assert admin_client.post(f'{COMMISSION}/payouts', json={}).status_code == 400

    payout_id = CEOPayoutId()
    assert admin_client.post(f'{COMMISSION}/payouts/{payout_id}/complete').status_code == 200
    assert {e.status for e in PlatformEarning.query.all()} == {'paid'}
    again = admin_client.post(f'{COMMISSION}/payouts/{payout_id}/complete')
    assert again.status_code == 200 and 'déjà' in again.get_json()['message']


def CEOPayoutId():
    from app.models import CEOPayout
    return CEOPayout.query.one().id


def test_two_payouts_in_the_same_second_get_distinct_references(admin_client, investor, project):
    from app.models import CEOPayout
    completed_contribution(investor, project)
    assert admin_client.post(f'{COMMISSION}/payouts', json={}).status_code == 201
    completed_contribution(investor, project)
    assert admin_client.post(f'{COMMISSION}/payouts', json={}).status_code == 201
    references = [p.payout_reference for p in CEOPayout.query.all()]
    assert len(references) == len(set(references)) == 2


@pytest.mark.parametrize('fee', [-1, 'abc', 10 ** 6])
def test_payout_rejects_invalid_transfer_fee(admin_client, investor, project, fee):
    completed_contribution(investor, project)
    assert admin_client.post(f'{COMMISSION}/payouts', json={'transfer_fee': fee}).status_code == 400
    assert {e.status for e in PlatformEarning.query.all()} == {'pending'}


def test_failed_payout_cannot_be_completed(admin_client, investor, project):
    from app.models import CEOPayout
    completed_contribution(investor, project)
    admin_client.post(f'{COMMISSION}/payouts', json={})
    payout = CEOPayout.query.one()
    payout.status = 'failed'
    db.session.commit()
    assert admin_client.post(f'{COMMISSION}/payouts/{payout.id}/complete').status_code == 409
    assert {e.status for e in PlatformEarning.query.all()} == {'pending_payout'}


def test_earnings_summary_and_totals_exclude_cancelled(admin_client, investor, project):
    kept = completed_contribution(investor, project, '1000.00')
    refunded = completed_contribution(investor, project, '2000.00')
    refunded.mark_refunded()
    summary = admin_client.get(f'{COMMISSION}/earnings/summary?period=month').get_json()
    assert summary['total_earnings_htg'] == 30.0
    assert sum(p['total'] for p in summary['by_project']) == 30.0
    assert admin_client.get(f'{COMMISSION}/earnings').get_json()['total_amount'] == 30.0
    assert kept.status == ContributionStatus.COMPLETED


# ----------------------------------------------------------- transferts de fonds
def batch_payload(ids, **extra):
    return {'contribution_ids': ids, 'destination_bank': 'Unibank', 'destination_account': '123',
            'beneficiary_name': 'AgriInvest', **extra}


@pytest.mark.parametrize('payload', [
    {}, {'contribution_ids': 'abc'}, {'contribution_ids': [True]}, {'contribution_ids': [1]},
    {'contribution_ids': [1], 'destination_bank': 'b', 'destination_account': 'a'}])
def test_batch_requires_valid_input(admin_client, payload):
    assert admin_client.post(f'{TRANSFERS}/batches', json=payload).status_code == 400
    assert FundTransfer.query.count() == 0


def test_batch_only_includes_valid_contributions_and_reports_the_rest(admin_client, investor, project):
    good = completed_contribution(investor, project, '1000.00')
    pending = Contribution(investor_id=investor.id, project_id=project.id, amount=Decimal('500'), currency='HTG',
                           amount_htg=Decimal('500'), payment_method='cash')
    db.session.add(pending)
    db.session.commit()
    resp = admin_client.post(f'{TRANSFERS}/batches', json=batch_payload([good.id, pending.id, 9999]))
    assert resp.status_code == 201
    body = resp.get_json()
    assert sorted(body['skipped_contribution_ids']) == sorted([pending.id, 9999])
    transfer = FundTransfer.query.one()
    assert json.loads(transfer.contribution_ids) == [good.id]
    assert transfer.amount_htg == Decimal('1000.00')
    # une contribution déjà dans un lot ne peut pas être reprise
    assert admin_client.post(f'{TRANSFERS}/batches', json=batch_payload([good.id])).status_code == 400


def test_completing_a_batch_does_not_change_contribution_status(admin_client, investor, project):
    c = completed_contribution(investor, project, '1000.00')
    other = completed_contribution(investor, project, '700.00')  # hors lot
    admin_client.post(f'{TRANSFERS}/batches', json=batch_payload([c.id]))
    transfer = FundTransfer.query.one()
    assert admin_client.put(f'{TRANSFERS}/batches/{transfer.id}/status', json={'status': 'completed'}).status_code == 200
    assert db.session.get(Contribution, c.id).status == ContributionStatus.COMPLETED
    assert db.session.get(Contribution, other.id).status == ContributionStatus.COMPLETED
    summary = admin_client.get(f'{TRANSFERS}/summary').get_json()
    assert summary['total_collected_htg'] == 1700.0
    assert summary['total_transferred_htg'] == 1000.0
    assert summary['pending_transfer_htg'] == 700.0  # jamais négatif


def test_batch_status_transitions_are_enforced(admin_client, investor, project):
    c = completed_contribution(investor, project)
    admin_client.post(f'{TRANSFERS}/batches', json=batch_payload([c.id]))
    url = f'{TRANSFERS}/batches/{FundTransfer.query.one().id}/status'
    assert admin_client.put(url, json={'status': 'bogus'}).status_code in (400, 409)
    assert admin_client.put(url, json={'status': 'processing'}).status_code == 200
    assert admin_client.put(url, json={'status': 'completed'}).status_code == 200
    assert admin_client.put(url, json={'status': 'pending'}).status_code == 409  # un lot terminé est figé
    assert admin_client.put(url, json={'status': 'completed'}).status_code == 200  # idempotent


def test_failed_batch_releases_its_contributions(admin_client, investor, project):
    c = completed_contribution(investor, project)
    admin_client.post(f'{TRANSFERS}/batches', json=batch_payload([c.id]))
    transfer = FundTransfer.query.one()
    assert db.session.get(Contribution, c.id).transfer_batch_id == transfer.batch_id
    admin_client.put(f'{TRANSFERS}/batches/{transfer.id}/status', json={'status': 'failed'})
    assert db.session.get(Contribution, c.id).transfer_batch_id is None
    assert admin_client.post(f'{TRANSFERS}/batches', json=batch_payload([c.id])).status_code == 201


def test_batched_contribution_cannot_be_refunded(admin_client, investor, project):
    c = completed_contribution(investor, project)
    admin_client.post(f'{TRANSFERS}/batches', json=batch_payload([c.id]))
    resp = admin_client.post(f'/api/v1/contributions/{c.id}/refund')
    assert resp.status_code == 409
    assert db.session.get(Contribution, c.id).status == ContributionStatus.COMPLETED


def test_transfer_endpoints_are_admin_only(client, investor, admin):
    login_as(client, investor)
    assert client.get(f'{TRANSFERS}/summary').status_code == 403
    assert client.post(f'{TRANSFERS}/batches', json=batch_payload([1])).status_code == 403
    assert client.get(f'{TRANSFERS}/batches/1').status_code == 403


# ----------------------------------------------------------------- administration
def test_banned_user_loses_access_immediately(client, investor, admin):
    login_as(client, investor)
    assert client.get('/api/v1/auth/me').status_code == 200
    login_as(client, admin)
    assert client.post(f'{ADMIN}/users/{investor.id}/ban').status_code == 200
    login_as(client, investor)
    assert client.get('/api/v1/auth/me').status_code == 401
    login_as(client, admin)
    client.post(f'{ADMIN}/users/{investor.id}/unban')
    login_as(client, investor)
    assert client.get('/api/v1/auth/me').status_code == 200


def test_admin_cannot_ban_themselves(admin_client, admin):
    assert admin_client.post(f'{ADMIN}/users/{admin.id}/ban').status_code == 400
    assert db.session.get(User, admin.id).is_active is True


def test_approve_and_reject_only_apply_to_pending_projects(admin_client, project):
    project.status = 'pending'
    project.is_published = False
    db.session.commit()
    assert admin_client.post(f'{ADMIN}/projects/{project.id}/approve').status_code == 200
    assert db.session.get(Project, project.id).status == 'published'
    assert admin_client.post(f'{ADMIN}/projects/{project.id}/approve').status_code == 409
    project.status = 'funded'
    db.session.commit()
    assert admin_client.post(f'{ADMIN}/projects/{project.id}/approve').status_code == 409
    assert admin_client.post(f'{ADMIN}/projects/{project.id}/reject').status_code == 409
    assert db.session.get(Project, project.id).status == 'funded'  # jamais ramené à « published » / « draft »


def test_reject_without_body_does_not_crash(admin_client, project):
    project.status = 'pending'
    db.session.commit()
    assert admin_client.post(f'{ADMIN}/projects/{project.id}/reject').status_code == 200
    assert db.session.get(Project, project.id).status == 'draft'


def test_admin_dashboard_and_user_listing(admin_client, investor):
    body = admin_client.get(f'{ADMIN}/dashboard').get_json()
    assert body['stats']['total_users'] >= 2
    assert admin_client.get(f'{ADMIN}/users?role=investor').status_code == 200
