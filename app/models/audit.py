# app/models/audit.py
"""Journal d'audit des actions sensibles (administration, argent, encaissement d'espèces)."""

from datetime import datetime, timezone

from sqlalchemy import Index

from app.extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)

    # Qui : l'identifiant peut disparaître (SET NULL), l'adresse e-mail est conservée telle quelle
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    actor_email = db.Column(db.String(120), nullable=True)

    # Quoi : action « domaine.verbe » (ex. user.ban, payout.create, cash.receive) et cible
    action = db.Column(db.String(60), nullable=False, index=True)
    target_type = db.Column(db.String(40), nullable=True)
    target_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)  # JSON : valeurs avant / après, montants, références

    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False, index=True)

    __table_args__ = (
        Index('idx_audit_logs_target', 'target_type', 'target_id'),
        Index('idx_audit_logs_actor', 'actor_id', 'created_at'),
    )

    def to_dict(self):
        import json
        try:
            details = json.loads(self.details) if self.details else None
        except ValueError:
            details = self.details
        return {
            'id': self.id,
            'actor_id': self.actor_id,
            'actor_email': self.actor_email,
            'action': self.action,
            'target_type': self.target_type,
            'target_id': self.target_id,
            'details': details,
            'ip_address': self.ip_address,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
