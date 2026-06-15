"""
Modèle pour la configuration des passerelles de paiement
"""

from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Index, UniqueConstraint
from app.extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class PaymentGatewayConfig(db.Model):
    __tablename__ = 'payment_gateway_configs'

    id = db.Column(db.Integer, primary_key=True)
    
    country_code = db.Column(db.String(2), nullable=False, index=True)
    gateway_name = db.Column(db.String(30), nullable=False, index=True)
    
    api_key = db.Column(db.Text, nullable=True)
    api_secret = db.Column(db.Text, nullable=True)
    webhook_secret = db.Column(db.Text, nullable=True)
    publishable_key = db.Column(db.Text, nullable=True)
    
    is_active = db.Column(db.Boolean, default=True)
    is_test_mode = db.Column(db.Boolean, default=True)
    currencies_supported = db.Column(db.String(100), nullable=True)
    
    fee_percentage = db.Column(db.Numeric(5, 2), default=2.9)
    fee_fixed = db.Column(db.Numeric(10, 2), default=0.30)
    fee_currency = db.Column(db.String(3), default='USD')
    
    stripe_connect_account_id = db.Column(db.String(100), nullable=True)
    stripe_connect_onboarding_completed = db.Column(db.Boolean, default=False)
    
    moncash_client_id = db.Column(db.String(100), nullable=True)
    moncash_client_secret = db.Column(db.Text, nullable=True)
    moncash_environment = db.Column(db.String(20), default='sandbox')
    
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    __table_args__ = (
        UniqueConstraint('country_code', 'gateway_name', name='uq_country_gateway'),
        Index('idx_payment_gateway_active', 'is_active', 'country_code'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'country_code': self.country_code,
            'gateway_name': self.gateway_name,
            'is_active': self.is_active,
            'currencies_supported': self.currencies_supported.split(',') if self.currencies_supported else [],
            'fee_percentage': float(self.fee_percentage),
            'publishable_key': self.publishable_key,
            'moncash_environment': self.moncash_environment,
        }