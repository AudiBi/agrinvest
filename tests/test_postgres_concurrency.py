"""Verrous de ligne (SELECT ... FOR UPDATE) : sans effet sous SQLite, vérifiés ici sous PostgreSQL.

Lancer avec TEST_DATABASE_URL=postgresql://... ; ignoré sinon.
Principe, déterministe : une transaction externe verrouille la ligne, la requête HTTP doit ATTENDRE ;
quand la transaction externe modifie la ligne puis valide, la requête reprend et voit le nouvel état.
"""
import threading
import time
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.extensions import db
from app.models import CollectionPoint, Contribution, PlatformEarning, ProjectCollectionPoint
from app.models.enums import ContributionStatus, UserRole
from tests.conftest import login_as, make_user

pytestmark = pytest.mark.skipif(
    not __import__('os').environ.get('TEST_DATABASE_URL', '').startswith('postgresql'),
    reason='nécessite PostgreSQL (TEST_DATABASE_URL)')


def call_in_thread(client, method, url, **kwargs):
    """Lance la requête dans un thread ; retourne (thread, résultat)."""
    result = {}

    def run():
        result['response'] = client.open(url, method=method, **kwargs)

    thread = threading.Thread(target=run)
    thread.start()
    return thread, result


def cash_contribution(investor, project):
    c = Contribution(investor_id=investor.id, project_id=project.id, amount=Decimal('1000'), currency='HTG',
                     amount_htg=Decimal('1000'), payment_method='cash')
    db.session.add(c)
    db.session.commit()
    return c


def test_payout_waits_for_locked_earnings_then_sees_they_are_taken(client, admin, investor, project):
    c = cash_contribution(investor, project)
    c.mark_completed()
    login_as(client, admin)

    with db.engine.connect() as other:
        transaction = other.begin()
        other.execute(text("SELECT id FROM platform_earnings WHERE status = 'pending' FOR UPDATE"))

        thread, result = call_in_thread(client, 'POST', '/api/v1/commission/payouts', json={})
        time.sleep(1.5)
        assert thread.is_alive(), 'la requête aurait dû attendre le verrou des lignes'

        other.execute(text("UPDATE platform_earnings SET status = 'pending_payout'"))
        transaction.commit()
        thread.join(timeout=10)

    assert not thread.is_alive()
    assert result['response'].status_code == 400  # plus rien à verser : pas de double versement
    assert PlatformEarning.query.filter_by(status='pending_payout').count() == 1


def test_cash_receipt_waits_for_locked_contribution_then_refuses_replay(client, investor, project):
    agent = make_user('agent@example.com', role=UserRole.AGENT)
    point = CollectionPoint(name='P', department='Nord', commune='Cap', address='Rue', fee_percentage=Decimal('0'))
    db.session.add(point)
    db.session.flush()
    db.session.add(ProjectCollectionPoint(project_id=project.id, collection_point_id=point.id))
    c = cash_contribution(investor, project)
    db.session.commit()
    login_as(client, agent)

    with db.engine.connect() as other:
        transaction = other.begin()
        other.execute(text(f"SELECT id FROM contributions WHERE id = {c.id} FOR UPDATE"))

        thread, result = call_in_thread(
            client, 'POST', f'/api/v1/collection-points/{point.id}/receive-cash',
            json={'contribution_id': c.id, 'amount': '1000', 'receipt_number': 'R-RACE'})
        time.sleep(1.5)
        assert thread.is_alive(), 'la requête aurait dû attendre le verrou de la contribution'

        other.execute(text(f"UPDATE contributions SET status = 'completed' WHERE id = {c.id}"))
        transaction.commit()
        thread.join(timeout=10)

    assert result['response'].status_code == 409  # déjà encaissée par ailleurs
    db.session.expire_all()
    assert db.session.get(Contribution, c.id).cash_receipt_number is None
    assert db.session.get(Contribution, c.id).status == ContributionStatus.COMPLETED


def test_transfer_batch_waits_for_locked_contributions(client, admin, investor, project):
    c = cash_contribution(investor, project)
    c.mark_completed()
    login_as(client, admin)
    payload = {'contribution_ids': [c.id], 'destination_bank': 'Unibank', 'destination_account': '1',
               'beneficiary_name': 'AgriInvest'}

    with db.engine.connect() as other:
        transaction = other.begin()
        other.execute(text(f"SELECT id FROM contributions WHERE id = {c.id} FOR UPDATE"))

        thread, result = call_in_thread(client, 'POST', '/api/v1/transfers/batches', json=payload)
        time.sleep(1.5)
        assert thread.is_alive(), 'la requête aurait dû attendre le verrou'

        other.execute(text(f"UPDATE contributions SET transfer_batch_id = 'BATCH-AILLEURS' WHERE id = {c.id}"))
        transaction.commit()
        thread.join(timeout=10)

    assert result['response'].status_code == 400  # déjà dans un autre lot : jamais transférée deux fois
