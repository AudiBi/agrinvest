from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import Contribution, Project, User
from app.models.enums import ContributionStatus, ProjectStatus, UserRole


@pytest.fixture()
def login(client, investor):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(investor.id)
        sess['_fresh'] = True
    return client


def invest(client, project, **form):
    return client.post(f'/invest/{project.id}', data=form)


@pytest.mark.parametrize('amount', ['-500', '0', 'Infinity', 'NaN', 'abc'])
def test_invalid_amounts_create_nothing(login, project, amount):
    resp = invest(login, project, amount=amount, payment_method='cash')
    assert resp.status_code == 302
    assert Contribution.query.count() == 0


def test_unknown_payment_method_rejected(login, project):
    invest(login, project, amount='500', payment_method='bitcoin')
    assert Contribution.query.count() == 0


def test_cash_stays_pending(login, project):
    invest(login, project, amount='500', payment_method='cash')
    c = Contribution.query.one()
    assert c.status == ContributionStatus.PENDING
    assert c.currency == 'HTG'


def test_moncash_redirects_to_gateway_and_stores_id(login, project, monkeypatch):
    monkeypatch.setattr('app.utils.payments.process_moncash_payment',
                        lambda c: {'payment_id': 'mc_1', 'approval_url': 'https://pay.example/mc_1'})
    resp = invest(login, project, amount='500', payment_method='moncash')
    assert resp.headers['Location'] == 'https://pay.example/mc_1'
    c = Contribution.query.one()
    assert c.moncash_payment_id == 'mc_1'
    assert c.status == ContributionStatus.PENDING


def test_gateway_failure_marks_failed(login, project, monkeypatch):
    def boom(c):
        raise RuntimeError('down')

    monkeypatch.setattr('app.utils.payments.process_paypal_payment', boom)
    invest(login, project, amount='500', payment_method='paypal')
    assert Contribution.query.one().status == ContributionStatus.FAILED


def test_stripe_charges_usd_at_current_rate(login, project, monkeypatch):
    monkeypatch.setattr('app.utils.exchange_rates.get_exchange_rate',
                        lambda a, b='HTG': Decimal('130'))
    monkeypatch.setattr('app.utils.payments.process_stripe_payment', lambda c: {'id': 'pi_1'})
    resp = invest(login, project, amount='1300', payment_method='stripe')
    c = Contribution.query.one()
    assert resp.headers['Location'].endswith(f'/payment/card/{c.id}')
    assert (c.currency, c.amount, c.stripe_payment_intent_id) == ('USD', Decimal('10.00'), 'pi_1')
    assert c.amount_htg == Decimal('1300.00')


def test_contract_requires_completed_contribution(login, project, investor):
    c = Contribution(investor_id=investor.id, project_id=project.id, amount=Decimal('500'),
                     currency='HTG', amount_htg=Decimal('500'), payment_method='cash')
    db.session.add(c)
    db.session.commit()
    resp = login.get(f'/contribution/{c.id}/contract')
    assert resp.status_code == 302
    assert '/dashboard' in resp.headers['Location']


def test_card_page_is_private_to_owner(client, project, investor):
    c = Contribution(investor_id=investor.id, project_id=project.id, amount=Decimal('10'),
                     currency='USD', amount_htg=Decimal('1300'), payment_method='stripe',
                     stripe_payment_intent_id='pi_1')
    db.session.add(c)
    db.session.commit()
    assert client.get(f'/payment/card/{c.id}').status_code == 302  # non connecté -> login
