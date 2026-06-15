"""
Modèles pour les transferts internationaux de fonds
"""

from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Index
from app.extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class FundTransfer(db.Model):
    __tablename__ = 'fund_transfers'

    id = db.Column(db.Integer, primary_key=True)
    
    batch_id = db.Column(db.String(50), nullable=False, index=True)
    
    source_country = db.Column(db.String(2), nullable=False)
    source_gateway = db.Column(db.String(30), nullable=False)
    source_account = db.Column(db.String(100), nullable=True)
    
    destination_bank = db.Column(db.String(50), nullable=False)
    destination_account = db.Column(db.String(50), nullable=False)
    beneficiary_name = db.Column(db.String(100), nullable=False)
    beneficiary_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    amount_source_currency = db.Column(db.Numeric(12, 2), nullable=False)
    source_currency = db.Column(db.String(3), nullable=False)
    exchange_rate = db.Column(db.Numeric(12, 6), nullable=False)
    amount_htg = db.Column(db.Numeric(12, 2), nullable=False)
    
    transfer_fee = db.Column(db.Numeric(10, 2), default=0)
    intermediary_bank_fee = db.Column(db.Numeric(10, 2), default=0)
    total_fees_htg = db.Column(db.Numeric(12, 2), default=0)
    
    transfer_method = db.Column(db.String(30), nullable=False)
    
    transfer_reference = db.Column(db.String(100), unique=True, nullable=False)
    external_transaction_id = db.Column(db.String(100), nullable=True)
    
    contribution_ids = db.Column(db.Text, nullable=True)
    
    status = db.Column(db.String(20), default='pending')
    
    initiated_at = db.Column(db.DateTime, default=utc_now)
    completed_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        Index('idx_fund_transfers_batch', 'batch_id', 'status'),
        Index('idx_fund_transfers_beneficiary', 'beneficiary_id', 'status'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'batch_id': self.batch_id,
            'source_country': self.source_country,
            'amount_source_currency': float(self.amount_source_currency),
            'source_currency': self.source_currency,
            'amount_htg': float(self.amount_htg),
            'transfer_method': self.transfer_method,
            'status': self.status,
            'initiated_at': self.initiated_at.isoformat() if self.initiated_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class InternationalTransferPartner(db.Model):
    __tablename__ = 'international_transfer_partners'

    id = db.Column(db.Integer, primary_key=True)
    
    name = db.Column(db.String(50), nullable=False)
    countries_from = db.Column(db.Text, nullable=False)
    
    api_endpoint = db.Column(db.String(200), nullable=True)
    api_key = db.Column(db.Text, nullable=True)
    webhook_secret = db.Column(db.Text, nullable=True)
    
    estimated_delivery_days = db.Column(db.Integer, default=3)
    fee_percentage = db.Column(db.Numeric(5, 2), default=0)
    fee_fixed = db.Column(db.Numeric(10, 2), default=0)
    fee_currency = db.Column(db.String(3), default='USD')
    
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'countries_from': self.countries_from,
            'estimated_delivery_days': self.estimated_delivery_days,
            'fee_percentage': float(self.fee_percentage),
            'is_active': self.is_active,
        }