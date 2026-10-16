from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.extensions import db
from app.models import Contribution
from app.models.contribution import utc_now
from app.models.enums import ContributionStatus
from app.utils import payments
from app.utils.reconciliation import reconcile_pending_contributions


def make_contribution(investor, project, method='stripe', status=ContributionStatus.PENDING,
                      amount='10.00', currency='USD', age_minutes=60, **extra):
    c = Contribution(investor_id=investor.id, project_id=project.id, amount=Decimal(amount),
                     currency=currency, amount_htg=Decimal(amount) * 130, payment_method=method,
                     status=status, **extra)
    db.session.add(c)
    db.session.commit()
    c.created_at = utc_now().replace(tzinfo=None) - timedelta(minutes=age_minutes)
    db.session.commit()
    return c


def stripe_event(intent_id, amount_minor, currency='usd'):
    return {'type': 'payment_intent.succeeded', 'data': {'object': {
        'id': intent_id, 'amount': amount_minor, 'amount_received': amount_minor, 'currency': currency}}}


@pytest.mark.parametrize('amount,currency,ok', [
    ('10.00', 'USD', True), (Decimal('10'), 'usd', True), ('9.99', 'USD', False),
    ('10.00', 'EUR', False), (None, 'USD', False), ('abc', 'USD', False)])
def test_payment_matches(amount, currency, ok):
    c = SimpleNamespace(amount=Decimal('10.00'), currency='USD')
    assert payments.payment_matches(c, amount, currency) is ok


def stripe_webhook(client, monkeypatch, event):
    monkeypatch.setattr('stripe.Webhook.construct_event', lambda *a, **k: event)
    return client.post('/api/v1/payments/webhook/stripe', data='{}', headers={'Stripe-Signature': 'x'})


def test_stripe_webhook_rejects_wrong_amount(client, investor, project, monkeypatch):
    c = make_contribution(investor, project, stripe_payment_intent_id='pi_1')
    stripe_webhook(client, monkeypatch, stripe_event('pi_1', 100))  # 1,00 USD payé au lieu de 10,00
    assert db.session.get(Contribution, c.id).status == ContributionStatus.PENDING


def test_stripe_webhook_confirms_exact_amount_once(client, investor, project, monkeypatch):
    c = make_contribution(investor, project, stripe_payment_intent_id='pi_1')
    for _ in range(2):  # rejeu du même webhook
        stripe_webhook(client, monkeypatch, stripe_event('pi_1', 1000))
    assert db.session.get(Contribution, c.id).status == ContributionStatus.COMPLETED
    assert db.session.get(type(project), project.id).amount_raised == c.amount_htg


def test_replayed_webhook_does_not_resurrect_refunded(client, investor, project, monkeypatch):
    c = make_contribution(investor, project, status=ContributionStatus.REFUNDED,
                          stripe_payment_intent_id='pi_1')
    stripe_webhook(client, monkeypatch, stripe_event('pi_1', 1000))
    assert db.session.get(Contribution, c.id).status == ContributionStatus.REFUNDED


def test_late_payment_confirms_a_failed_contribution(client, investor, project, monkeypatch):
    c = make_contribution(investor, project, status=ContributionStatus.FAILED,
                          stripe_payment_intent_id='pi_1')
    stripe_webhook(client, monkeypatch, stripe_event('pi_1', 1000))
    assert db.session.get(Contribution, c.id).status == ContributionStatus.COMPLETED


def test_moncash_failed_webhook_does_not_touch_refunded(client, app, investor, project):
    import hashlib, hmac, json
    c = make_contribution(investor, project, method='moncash', currency='HTG', amount='1000.00',
                          status=ContributionStatus.REFUNDED, moncash_payment_id='mc_1')
    body = json.dumps({'payment_id': 'mc_1', 'status': 'failed'}).encode()
    sig = hmac.new(b'moncash-test-secret', body, hashlib.sha256).hexdigest()
    client.post('/api/v1/webhooks/moncash', data=body,
                headers={'Content-Type': 'application/json', 'X-MonCash-Signature': sig})
    assert db.session.get(Contribution, c.id).status == ContributionStatus.REFUNDED


def test_reconcile_confirms_expires_and_skips(app, investor, project, monkeypatch):
    paid = make_contribution(investor, project, stripe_payment_intent_id='pi_paid')
    abandoned = make_contribution(investor, project, stripe_payment_intent_id='pi_old',
                                  age_minutes=60 * 30)
    recent = make_contribution(investor, project, stripe_payment_intent_id='pi_new', age_minutes=2)
    cash = make_contribution(investor, project, method='cash', age_minutes=60 * 48)

    ids = {paid.id: True}
    monkeypatch.setattr('app.utils.reconciliation.verify_payment', lambda c: ids.get(c.id, False))

    stats = reconcile_pending_contributions()

    assert stats == {'checked': 2, 'completed': 1, 'expired': 1, 'errors': 0}
    assert db.session.get(Contribution, paid.id).status == ContributionStatus.COMPLETED
    assert db.session.get(Contribution, abandoned.id).status == ContributionStatus.FAILED
    assert db.session.get(Contribution, recent.id).status == ContributionStatus.PENDING
    assert db.session.get(Contribution, cash.id).status == ContributionStatus.PENDING


def test_reconcile_survives_a_gateway_error(app, investor, project, monkeypatch):
    c = make_contribution(investor, project, stripe_payment_intent_id='pi_x')

    def boom(contribution):
        raise RuntimeError('gateway down')

    monkeypatch.setattr('app.utils.reconciliation.verify_payment', boom)
    stats = reconcile_pending_contributions()
    assert stats['errors'] == 1
    assert db.session.get(Contribution, c.id).status == ContributionStatus.PENDING


def test_commission_fallback_works_with_empty_config_table(app, project):
    """Base neuve sans PlatformCommissionConfig : la commission par défaut (3 %) doit s'appliquer."""
    config = project.get_commission_config()
    assert config.calculate_commission(Decimal('1000')) == Decimal('30')


def test_mark_completed_records_commission_and_credits_project(app, investor, project):
    from app.models.platform_commission import PlatformEarning
    c = make_contribution(investor, project, currency='HTG', amount='1000.00')
    c.amount_htg = Decimal('1000.00')  # le helper applique un taux de 130
    db.session.commit()
    c.mark_completed()
    earning = PlatformEarning.query.filter_by(contribution_id=c.id).one()
    assert earning.commission_amount_htg == Decimal('30.00')  # 3 % par défaut
    assert earning.net_to_project == Decimal('970.00')
    assert db.session.get(type(project), project.id).amount_raised == Decimal('1000.00')
