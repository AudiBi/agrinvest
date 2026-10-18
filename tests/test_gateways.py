from decimal import Decimal

from app.extensions import db
from app.models import Contribution
from app.models.enums import ContributionStatus
from tests.conftest import login_as
from tests.test_invest import login  # noqa: F401  (fixture)
from tests.test_reconciliation import make_contribution, stripe_webhook


def refund_event(intent_id, refunded=True):
    return {'type': 'charge.refunded', 'data': {'object': {
        'payment_intent': intent_id, 'refunded': refunded}}}


# ------------------------------------------------------------------ Stripe
def test_stripe_full_refund_marks_refunded_once(client, investor, project, monkeypatch):
    c = make_contribution(investor, project, status=ContributionStatus.COMPLETED,
                          stripe_payment_intent_id='pi_1')
    project.amount_raised = c.amount_htg
    db.session.commit()
    for _ in range(2):  # webhook rejoué : la déduction ne se fait qu'une fois
        stripe_webhook(client, monkeypatch, refund_event('pi_1'))
    assert db.session.get(Contribution, c.id).status == ContributionStatus.REFUNDED
    assert db.session.get(type(project), project.id).amount_raised == 0


def test_stripe_partial_refund_is_not_applied(client, investor, project, monkeypatch):
    c = make_contribution(investor, project, status=ContributionStatus.COMPLETED,
                          stripe_payment_intent_id='pi_1')
    stripe_webhook(client, monkeypatch, refund_event('pi_1', refunded=False))
    assert db.session.get(Contribution, c.id).status == ContributionStatus.COMPLETED


# ------------------------------------------------------------------ PayPal
class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def test_capture_paypal_order_sends_idempotency_key(app, monkeypatch):
    from app.utils import paypal
    calls = []
    monkeypatch.setattr(paypal, 'get_paypal_access_token', lambda: 'tok')

    def fake_post(url, **kwargs):
        calls.append((url, kwargs['headers']))
        return FakeResponse({'status': 'COMPLETED'})

    monkeypatch.setattr(paypal.requests, 'post', fake_post)
    assert paypal.capture_paypal_order('ORDER1') == {'status': 'COMPLETED'}
    url, headers = calls[0]
    assert url.endswith('/checkout/orders/ORDER1/capture')
    assert headers['PayPal-Request-Id'] == 'capture-ORDER1'


def test_capture_without_token_or_order_does_nothing(app, monkeypatch):
    from app.utils import paypal
    monkeypatch.setattr(paypal, 'get_paypal_access_token', lambda: None)
    assert paypal.capture_paypal_order('ORDER1') is None
    assert paypal.capture_paypal_order(None) is None


def test_order_approved_webhook_triggers_capture(app, monkeypatch):
    from app.utils import paypal
    captured = []
    monkeypatch.setattr(paypal, 'capture_paypal_order', captured.append)
    paypal._handle_order_approved({'id': 'ORDER1'})
    assert captured == ['ORDER1']


def test_paypal_return_captures_and_confirms_own_order(client, investor, project, monkeypatch):
    c = make_contribution(investor, project, method='paypal', paypal_order_id='ORDER1')
    monkeypatch.setattr('app.utils.paypal.capture_paypal_order', lambda oid: {'status': 'COMPLETED'})
    monkeypatch.setattr('app.utils.payments.verify_payment', lambda contribution: True)
    login_as(client, investor)
    client.get('/payment/success?token=ORDER1')
    assert db.session.get(Contribution, c.id).status == ContributionStatus.COMPLETED


def test_paypal_return_ignores_someone_elses_order(client, investor, other_investor, project, monkeypatch):
    c = make_contribution(investor, project, method='paypal', paypal_order_id='ORDER1')
    captured = []
    monkeypatch.setattr('app.utils.paypal.capture_paypal_order', lambda oid: captured.append(oid) or {})
    login_as(client, other_investor)
    client.get('/payment/success?token=ORDER1')
    assert captured == []
    assert db.session.get(Contribution, c.id).status == ContributionStatus.PENDING


def test_paypal_return_does_not_confirm_when_gateway_refuses(client, investor, project, monkeypatch):
    c = make_contribution(investor, project, method='paypal', paypal_order_id='ORDER1')
    monkeypatch.setattr('app.utils.paypal.capture_paypal_order', lambda oid: {'status': 'COMPLETED'})
    monkeypatch.setattr('app.utils.payments.verify_payment', lambda contribution: False)
    login_as(client, investor)
    client.get('/payment/success?token=ORDER1')
    assert db.session.get(Contribution, c.id).status == ContributionStatus.PENDING


def test_paypal_from_web_form_is_charged_in_usd(login, project, monkeypatch):
    from tests.test_invest import invest
    monkeypatch.setattr('app.utils.exchange_rates.get_exchange_rate', lambda a, b='HTG': Decimal('130'))
    monkeypatch.setattr('app.utils.payments.process_paypal_payment',
                        lambda c: {'id': 'ORDER1', 'approval_url': 'https://paypal.example/approve'})
    resp = invest(login, project, amount='1300', payment_method='paypal')
    c = Contribution.query.one()
    assert resp.headers['Location'] == 'https://paypal.example/approve'
    assert (c.currency, c.amount, c.paypal_order_id) == ('USD', Decimal('10.00'), 'ORDER1')


def test_api_rejects_htg_for_card_and_paypal(client, investor, project):
    login_as(client, investor)
    for method in ('stripe', 'paypal'):
        resp = client.post(f'/api/v1/contributions/projects/{project.id}/invest',
                           json={'amount': 500, 'currency': 'HTG', 'payment_method': method})
        assert resp.status_code == 400
    assert Contribution.query.count() == 0
