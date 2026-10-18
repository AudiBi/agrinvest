# app/utils/reconciliation.py
"""Réconciliation des contributions restées « pending » (webhook perdu, paiement abandonné).

À exécuter périodiquement (cron / Celery beat) : `flask reconcile-payments`.
La passerelle fait foi : une contribution n'est confirmée que si verify_payment() le valide
(statut, identifiant stocké côté serveur, montant et devise). Les espèces ne sont jamais touchées.
"""

from datetime import timedelta

from flask import current_app

from app.extensions import db
from app.models import Contribution
from app.models.contribution import utc_now
from app.models.enums import ContributionStatus
from app.utils.payments import verify_payment

GATEWAY_METHODS = ('stripe', 'paypal', 'moncash')


def reconcile_pending_contributions(min_age_minutes=15, expire_after_hours=None):
    """Retourne {'checked', 'completed', 'expired', 'errors'}.

    - min_age_minutes : on laisse d'abord au webhook le temps d'arriver.
    - expire_after_hours : au-delà, une contribution non payée passe en « failed »
      (un paiement tardif reste confirmable par webhook, voir CONFIRMABLE_STATUSES).
    """
    if expire_after_hours is None:
        expire_after_hours = current_app.config.get('PENDING_PAYMENT_TTL_HOURS', 24)

    now = utc_now().replace(tzinfo=None)
    newer_than = now - timedelta(minutes=min_age_minutes)
    expire_before = now - timedelta(hours=expire_after_hours)
    stats = {'checked': 0, 'completed': 0, 'expired': 0, 'errors': 0}

    pending = Contribution.query.filter(
        Contribution.status == ContributionStatus.PENDING,
        Contribution.payment_method.in_(GATEWAY_METHODS),
        Contribution.created_at <= newer_than,
    ).all()

    for contribution in pending:
        stats['checked'] += 1
        try:
            if verify_payment(contribution):
                contribution.mark_completed()
                stats['completed'] += 1
            elif contribution.created_at <= expire_before:
                contribution.mark_failed()
                stats['expired'] += 1
        except Exception as e:  # une passerelle en panne ne doit pas bloquer les autres
            db.session.rollback()
            stats['errors'] += 1
            current_app.logger.error(f'Réconciliation contribution {contribution.id}: {e}')

    return stats
