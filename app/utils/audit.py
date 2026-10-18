# app/utils/audit.py
"""Enregistrement des actions sensibles dans le journal d'audit."""

import json

from flask import has_request_context, request
from flask_login import current_user

from app.extensions import db
from app.models.audit import AuditLog

MAX_DETAILS_LENGTH = 4000


def record_audit(action, target=None, target_type=None, target_id=None, **details):
    """Ajoute une entrée d'audit à la session SANS valider.

    À appeler juste avant le commit de l'action elle-même : l'action et sa trace sont alors
    validées (ou annulées) ensemble, il n'existe jamais d'action sans trace.

    `target` peut être un objet du modèle (type et identifiant déduits) ; sinon `target_type` /
    `target_id`. Ne jamais passer de secret dans `details` (clés, numéros de compte, mots de passe).
    """
    if target is not None:
        target_type = target_type or getattr(target, '__tablename__', type(target).__name__)
        target_id = target_id if target_id is not None else getattr(target, 'id', None)

    actor = current_user if current_user and current_user.is_authenticated else None
    payload = json.dumps(details, default=str, ensure_ascii=False) if details else None
    if payload and len(payload) > MAX_DETAILS_LENGTH:
        payload = payload[:MAX_DETAILS_LENGTH - 1] + '…'

    entry = AuditLog(
        actor_id=actor.id if actor else None,
        actor_email=actor.email if actor else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=payload,
        ip_address=request.remote_addr if has_request_context() else None,
    )
    db.session.add(entry)
    return entry
