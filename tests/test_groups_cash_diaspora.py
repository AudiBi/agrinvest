"""Cagnottes de groupe, encaissement des espèces aux points de collecte, campagnes diaspora."""
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import (CollectionPoint, CollectionPointAgent, Contribution, DiasporaCampaign, GroupContribution,
                        GroupContributionInvite, Notification, ProjectCollectionPoint, User)
from app.models.contribution import utc_now
from app.models.enums import ContributionStatus, UserRole
from tests.conftest import login_as, make_user


@pytest.fixture(autouse=True)
def fixed_rates(monkeypatch):
    def rate(from_currency, to_currency='HTG'):
        return Decimal('1') if from_currency == to_currency else Decimal('130')

    monkeypatch.setattr('app.utils.exchange_rates.get_exchange_rate', rate)


@pytest.fixture()
def group(project, investor):
    g = GroupContribution(project_id=project.id, created_by_id=investor.id, group_name='Famille',
                          group_type='family', target_amount=Decimal('100'), currency='USD')
    db.session.add(g)
    db.session.commit()
    return g


@pytest.fixture()
def agent(app):
    return make_user('agent@example.com', role=UserRole.AGENT, name='Agent')


@pytest.fixture()
def point(project, agent):
    p = CollectionPoint(name='Point Nord', department='Nord', commune='Cap', address='Rue 1',
                        fee_percentage=Decimal('2'))
    db.session.add(p)
    db.session.flush()
    db.session.add(ProjectCollectionPoint(project_id=project.id, collection_point_id=p.id))
    db.session.add(CollectionPointAgent(collection_point_id=p.id, agent_id=agent.id))
    db.session.commit()
    return p


def cash_contribution(investor, project, amount='1000.00'):
    c = Contribution(investor_id=investor.id, project_id=project.id, amount=Decimal(amount), currency='HTG',
                     amount_htg=Decimal(amount), payment_method='cash')
    db.session.add(c)
    db.session.commit()
    return c


# ============================================================ cagnottes de groupe
@pytest.mark.parametrize('extra', [
    {'target_amount': None}, {'target_amount': -5}, {'target_amount': 'abc'}, {'target_amount': 10, 'currency': 'XXX'},
    {'target_amount': 10, 'expires_at': 'pas une date'}, {'target_amount': 10, 'max_members': 0}])
def test_create_group_validates_input(client, investor, project, extra):
    login_as(client, investor)
    resp = client.post('/api/v1/groups', json={'project_id': project.id, 'group_name': 'G', **extra})
    assert resp.status_code == 400
    assert GroupContribution.query.count() == 0


def test_create_group_ok_and_non_json_body(client, investor, project):
    login_as(client, investor)
    ok = client.post('/api/v1/groups', json={'project_id': project.id, 'group_name': 'G', 'target_amount': 50,
                                             'expires_at': '2030-01-01T00:00:00Z'})
    assert ok.status_code == 201
    assert client.post('/api/v1/groups', data='nope', content_type='text/plain').status_code == 400


def test_private_group_is_hidden_from_strangers(client, group, other_investor, investor, admin):
    group.is_public = False
    db.session.commit()
    url = f'/api/v1/groups/{group.id}'
    assert client.get(url).status_code == 404
    login_as(client, other_investor)
    assert client.get(url).status_code == 404
    for allowed in (investor, admin):
        login_as(client, allowed)
        assert client.get(url).status_code == 200


def test_public_group_is_visible_and_serializable(client, group):
    resp = client.get(f'/api/v1/groups/{group.id}')
    assert resp.status_code == 200 and resp.get_json()['member_count'] == 0  # compatible SQLite


def test_invites_are_validated_and_creator_only(client, group, investor, other_investor):
    url = f'/api/v1/groups/{group.id}/invite'
    login_as(client, other_investor)
    assert client.post(url, json={'emails': ['a@example.com']}).status_code == 403
    login_as(client, investor)
    assert client.post(url, json={'emails': ['pas-un-email']}).status_code == 400
    assert client.post(url, json={'emails': [f'u{i}@example.com' for i in range(21)]}).status_code == 400
    assert client.post(url, json={'emails': 'a@example.com'}).status_code == 400
    ok = client.post(url, json={'emails': ['a@example.com'], 'phones': ['+50937000000']})
    assert ok.status_code == 201 and len(ok.get_json()['invites']) == 2


def test_invite_creation_works_at_the_end_of_the_month(group, investor, monkeypatch):
    """Régression : `replace(day=day + 7)` levait ValueError à partir du 25 de chaque mois."""
    end_of_month = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr('app.models.group_contribution.utc_now', lambda: end_of_month)
    invite = GroupContributionInvite(group_id=group.id, invited_by_id=investor.id, invite_email='a@example.com')
    assert invite.expires_at == end_of_month + timedelta(days=7)


def test_join_group_rules(client, group, investor, other_investor):
    invite = GroupContributionInvite(group_id=group.id, invited_by_id=investor.id, invite_email=other_investor.email)
    expired = GroupContributionInvite(group_id=group.id, invited_by_id=investor.id)
    expired.expires_at = utc_now().replace(tzinfo=None) - timedelta(days=1)
    db.session.add_all([invite, expired])
    db.session.commit()

    login_as(client, other_investor)
    assert client.post(f'/api/v1/groups/join/{expired.invite_code}').status_code == 404
    assert db.session.get(GroupContributionInvite, expired.id).status == 'expired'

    stranger = make_user('stranger@example.com')
    login_as(client, stranger)
    assert client.post(f'/api/v1/groups/join/{invite.invite_code}').status_code == 404  # adressée à un autre e-mail

    login_as(client, other_investor)
    assert client.post(f'/api/v1/groups/join/{invite.invite_code}').status_code == 200
    assert client.post(f'/api/v1/groups/join/{invite.invite_code}').status_code == 404  # déjà utilisée


def test_cannot_join_or_contribute_to_a_closed_group(client, group, other_investor, investor):
    invite = GroupContributionInvite(group_id=group.id, invited_by_id=investor.id)
    group.status = 'completed'
    db.session.add(invite)
    db.session.commit()
    login_as(client, other_investor)
    assert client.post(f'/api/v1/groups/join/{invite.invite_code}').status_code == 409
    resp = client.post(f'/api/v1/groups/{group.id}/contribute', json={'amount': 10, 'payment_method': 'stripe'})
    assert resp.status_code == 409


@pytest.mark.parametrize('payload', [
    {'amount': -1, 'payment_method': 'stripe'}, {'amount': 'x', 'payment_method': 'stripe'},
    {'amount': 10, 'payment_method': 'card'}, {'amount': 10}, {}])
def test_contribute_validates_input(client, group, other_investor, payload):
    login_as(client, other_investor)
    assert client.post(f'/api/v1/groups/{group.id}/contribute', json=payload).status_code == 400
    assert Contribution.query.count() == 0


def test_contribute_does_not_credit_the_group_before_payment(client, group, other_investor, monkeypatch):
    monkeypatch.setattr('app.api.group_contribution_routes.initiate_payment',
                        lambda c: {'id': 'pi_1', 'approval_url': 'https://pay.example/1'})
    login_as(client, other_investor)
    resp = client.post(f'/api/v1/groups/{group.id}/contribute', json={'amount': 40, 'payment_method': 'stripe'})
    assert resp.status_code == 201 and resp.get_json()['payment_url'] == 'https://pay.example/1'
    contribution = Contribution.query.one()
    assert contribution.status == ContributionStatus.PENDING
    assert contribution.amount_htg == Decimal('5200.00')  # 40 USD x 130 : plus de montant pris pour du HTG
    assert db.session.get(GroupContribution, group.id).current_amount == 0  # rien n'est crédité avant paiement


def test_group_is_credited_on_confirmation_and_debited_on_refund(group, investor, other_investor, project):
    c = Contribution(investor_id=other_investor.id, project_id=project.id, group_id=group.id,
                     amount=Decimal('100'), currency='USD', amount_htg=Decimal('13000'), payment_method='stripe')
    db.session.add(c)
    db.session.commit()
    c.mark_completed()
    c.mark_completed()  # idempotent : pas de double crédit
    group = db.session.get(GroupContribution, group.id)
    assert (group.current_amount, group.status, group.member_count) == (Decimal('100'), 'completed', 1)
    c.mark_refunded()
    group = db.session.get(GroupContribution, group.id)
    assert (group.current_amount, group.status) == (Decimal('0'), 'active')


def test_payment_failure_marks_contribution_failed(client, group, other_investor, monkeypatch):
    def boom(contribution):
        raise RuntimeError('gateway down')

    monkeypatch.setattr('app.api.group_contribution_routes.initiate_payment', boom)
    login_as(client, other_investor)
    resp = client.post(f'/api/v1/groups/{group.id}/contribute', json={'amount': 10, 'payment_method': 'paypal'})
    assert resp.status_code == 502
    assert Contribution.query.one().status == ContributionStatus.FAILED
    assert db.session.get(GroupContribution, group.id).current_amount == 0


def test_stripe_or_paypal_refuse_htg_groups(client, group, other_investor):
    group.currency = 'HTG'
    db.session.commit()
    login_as(client, other_investor)
    resp = client.post(f'/api/v1/groups/{group.id}/contribute', json={'amount': 10, 'payment_method': 'stripe'})
    assert resp.status_code == 400


# ===================================================================== espèces
def receive(client, point, **payload):
    return client.post(f'/api/v1/collection-points/{point.id}/receive-cash', json=payload)


def test_receive_cash_requires_an_agent(client, point, investor):
    assert receive(client, point).status_code == 401
    login_as(client, investor)
    assert receive(client, point).status_code == 403


def test_receive_cash_confirms_the_contribution(client, point, agent, investor, project):
    c = cash_contribution(investor, project, '1000.00')
    login_as(client, agent)
    resp = receive(client, point, contribution_id=c.id, amount='1000.00', receipt_number='R-001')
    assert resp.status_code == 200
    c = db.session.get(Contribution, c.id)
    assert (c.status, c.collection_point_id, c.cash_receipt_number) == (ContributionStatus.COMPLETED, point.id, 'R-001')
    assert c.gateway_fee == Decimal('20.00')  # 2 % de frais de collecte
    assert db.session.get(type(project), project.id).amount_raised == Decimal('1000.00')


def test_receive_cash_rejects_inconsistent_requests(client, point, agent, investor, project):
    c = cash_contribution(investor, project, '1000.00')
    login_as(client, agent)
    assert receive(client, point, contribution_id=c.id, amount='999', receipt_number='R-1').status_code == 400
    assert receive(client, point, contribution_id=c.id, amount='1000').status_code == 400          # reçu manquant
    assert receive(client, point, contribution_id=c.id, amount='abc', receipt_number='R-1').status_code == 400
    assert receive(client, point, contribution_id=999, amount='1', receipt_number='R-1').status_code == 404
    assert db.session.get(Contribution, c.id).status == ContributionStatus.PENDING


def test_receive_cash_refuses_unlinked_project_inactive_point_and_non_cash(client, point, agent, investor, project):
    login_as(client, agent)
    card = Contribution(investor_id=investor.id, project_id=project.id, amount=Decimal('10'), currency='HTG',
                        amount_htg=Decimal('10'), payment_method='stripe')
    db.session.add(card)
    db.session.commit()
    assert receive(client, point, contribution_id=card.id, amount='10', receipt_number='R-2').status_code == 404

    c = cash_contribution(investor, project)
    ProjectCollectionPoint.query.delete()
    db.session.commit()
    assert receive(client, point, contribution_id=c.id, amount='1000', receipt_number='R-3').status_code == 400

    point.is_active = False
    db.session.commit()
    assert receive(client, point, contribution_id=c.id, amount='1000', receipt_number='R-4').status_code == 409


def test_receive_cash_is_not_replayable_and_receipts_are_unique(client, point, agent, investor, project):
    first, second = cash_contribution(investor, project), cash_contribution(investor, project)
    login_as(client, agent)
    assert receive(client, point, contribution_id=first.id, amount='1000', receipt_number='R-9').status_code == 200
    assert receive(client, point, contribution_id=first.id, amount='1000', receipt_number='R-10').status_code == 409
    assert receive(client, point, contribution_id=second.id, amount='1000', receipt_number='R-9').status_code == 409
    assert db.session.get(type(project), project.id).amount_raised == Decimal('1000.00')


def test_collection_point_input_validation(client, admin, project):
    login_as(client, admin)
    base = {'name': 'P', 'department': 'Nord', 'commune': 'Cap', 'address': 'Rue'}
    assert client.post('/api/v1/collection-points', json={'name': 'P'}).status_code == 400
    for bad in ({'fee_percentage': 150}, {'fee_percentage': -1}, {'fee_percentage': 'x'},
                {'latitude': 200}, {'longitude': -500}, {'project_ids': [99999]}, {'project_ids': 'a'}):
        assert client.post('/api/v1/collection-points', json={**base, **bad}).status_code == 400, bad
    assert CollectionPoint.query.count() == 0
    ok = client.post('/api/v1/collection-points', json={**base, 'fee_percentage': 1.5, 'project_ids': [project.id]})
    assert ok.status_code == 201 and ProjectCollectionPoint.query.count() == 1


def test_nearby_accepts_zero_coordinates_and_rejects_invalid(client):
    assert client.get('/api/v1/collection-points/nearby?lat=0&lng=0').status_code == 200
    assert client.get('/api/v1/collection-points/nearby?lat=95&lng=0').status_code == 400
    assert client.get('/api/v1/collection-points/nearby').status_code == 400


# ===================================================================== diaspora
def diaspora_user(email='dia@example.com', country='US'):
    return make_user(email, country=country, name='Diaspora')


def test_applying_does_not_grant_the_ambassador_role(client, admin):
    user = diaspora_user()
    login_as(client, user)
    resp = client.post('/api/v1/diaspora/apply-ambassador', json={'diaspora_community': 'Miami'})
    assert resp.status_code == 202
    assert db.session.get(User, user.id).role == UserRole.INVESTOR  # le rôle n'est jamais auto-attribué
    note = Notification.query.filter_by(user_id=admin.id).one()
    assert json.loads(note.data)['user_id'] == user.id


def test_apply_eligibility(client, investor, farmer_user):
    login_as(client, investor)  # pays HT : pas de la diaspora
    assert client.post('/api/v1/diaspora/apply-ambassador', json={}).status_code == 400
    farmer = db.session.get(User, farmer_user.id)
    farmer.country = 'US'
    db.session.commit()
    login_as(client, farmer)
    assert client.post('/api/v1/diaspora/apply-ambassador', json={}).status_code == 400
    ambassador = make_user('amb@example.com', role=UserRole.AMBASSADOR, country='US')
    login_as(client, ambassador)
    assert client.post('/api/v1/diaspora/apply-ambassador', json={}).status_code == 200


def test_only_an_admin_can_grant_the_role(client, admin, investor):
    user = diaspora_user()
    login_as(client, user)
    assert client.post(f'/api/v1/admin/users/{user.id}/approve-ambassador').status_code == 403
    login_as(client, admin)
    assert client.post(f'/api/v1/admin/users/{investor.id}/approve-ambassador').status_code == 409  # pays HT
    assert client.post(f'/api/v1/admin/users/{user.id}/approve-ambassador').status_code == 200
    assert db.session.get(User, user.id).role == UserRole.AMBASSADOR
    assert client.get('/api/v1/diaspora/ambassadors').status_code == 200


def campaign_payload(project, **extra):
    return {'project_id': project.id, 'target_countries': ['us', 'CA'], **extra}


def test_create_campaign_validation_and_ownership(client, project, investor, admin):
    owner = db.session.get(User, project.farmer_id)
    login_as(client, investor)
    assert client.post('/api/v1/diaspora/campaigns', json=campaign_payload(project)).status_code == 403
    login_as(client, owner)
    for bad in ({'target_countries': []}, {'target_countries': ['USA']}, {'target_countries': 'US'},
                {'matching_fund_percentage': 150}, {'matching_fund_percentage': -5},
                {'ambassador_commission': 'x'}, {'matching_fund_cap': -1}, {'ambassador_id': investor.id},
                {'ambassador_id': 99999}, {'virtual_townhall_date': 'demain'}):
        assert client.post('/api/v1/diaspora/campaigns', json={**campaign_payload(project), **bad}).status_code == 400, bad
    assert client.post('/api/v1/diaspora/campaigns', json={}).status_code == 400
    assert DiasporaCampaign.query.count() == 0
    ok = client.post('/api/v1/diaspora/campaigns', json=campaign_payload(project, matching_fund_percentage=50))
    assert ok.status_code == 201
    assert json.loads(DiasporaCampaign.query.one().target_countries) == ['CA', 'US']  # normalisé


def make_campaign(project, countries=('US',)):
    campaign = DiasporaCampaign(project_id=project.id, target_countries=json.dumps(list(countries)),
                                matching_fund_cap=Decimal('1000'))
    db.session.add(campaign)
    db.session.commit()
    return campaign


def test_campaign_totals_follow_confirmed_contributions(project):
    campaign = make_campaign(project)
    abroad = diaspora_user()
    local = make_user('local@example.com', country='HT')
    contributions = []
    for user, country in ((abroad, 'US'), (local, 'HT')):
        c = Contribution(investor_id=user.id, project_id=project.id, amount=Decimal('500'), currency='HTG',
                         amount_htg=Decimal('500'), payment_method='cash', investor_country=country)
        db.session.add(c)
        db.session.commit()
        c.mark_completed()
        contributions.append(c)
    campaign = db.session.get(DiasporaCampaign, campaign.id)
    assert (campaign.contributions_count, campaign.total_amount_raised) == (1, Decimal('500'))  # seul le pays ciblé
    contributions[0].mark_refunded()
    campaign = db.session.get(DiasporaCampaign, campaign.id)
    assert (campaign.contributions_count, campaign.total_amount_raised) == (0, Decimal('0'))


def test_campaign_stats_never_report_negative_matching_fund(client, project):
    campaign = make_campaign(project)
    campaign.total_amount_raised = Decimal('5000')  # au-dessus du plafond de 1000
    db.session.commit()
    body = client.get(f'/api/v1/diaspora/campaigns/{campaign.id}/stats').get_json()
    assert body['matching_fund_available'] == 0
