from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.utils import exchange_rates, payments
from app.utils.date_utils import get_date_range, get_last_days, get_last_months


def test_last_days_ordered_and_bounded():
    days = get_last_days(3)
    assert len(days) == 3
    assert days[0]['start'] < days[-1]['start']
    assert days[0]['start'] <= days[0]['end']


def test_last_months_contiguous():
    months = get_last_months(14)
    assert len(months) == 14
    for prev, nxt in zip(months, months[1:]):
        assert (nxt['start'] - prev['end']).total_seconds() < 1


@pytest.mark.parametrize('period', ['day', 'week', 'month', 'year', 'unknown'])
def test_date_range(period):
    start, end = get_date_range(period)
    assert isinstance(start, datetime) and start <= end


def test_exchange_rate_same_currency_and_unsupported(app):
    assert exchange_rates.get_exchange_rate('HTG', 'HTG') == Decimal('1')
    with pytest.raises(ValueError):
        exchange_rates.get_exchange_rate('XXX', 'HTG')


def test_exchange_rate_unavailable_does_not_invent_a_rate(app, monkeypatch):
    exchange_rates._cache.clear()

    def boom(base):
        raise ValueError('down')

    monkeypatch.setattr(exchange_rates, '_fetch_rates', boom)
    with pytest.raises(RuntimeError):
        exchange_rates.get_exchange_rate('USD', 'HTG')


def test_verify_payment_fails_closed(app):
    no_id = SimpleNamespace(id=1, payment_method='stripe', stripe_payment_intent_id=None)
    assert payments.verify_payment(no_id, 'pi_x') is False
    mismatch = SimpleNamespace(id=1, payment_method='stripe', stripe_payment_intent_id='pi_real')
    assert payments.verify_payment(mismatch, 'pi_other') is False
    cash = SimpleNamespace(id=1, payment_method='cash')
    assert payments.verify_payment(cash, 'x') is False
    with pytest.raises(ValueError):
        payments.process_refund(cash)
