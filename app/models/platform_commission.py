"""
Modèles pour les commissions de la plateforme et du CEO
"""

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import Index, CheckConstraint
from app.extensions import db
from app.models.enums import CommissionType


def utc_now():
    return datetime.now(timezone.utc)


class PlatformCommissionConfig(db.Model):
    __tablename__ = 'platform_commission_configs'

    id = db.Column(db.Integer, primary_key=True)
    
    commission_type = db.Column(db.String(30), nullable=False)
    percentage = db.Column(db.Numeric(5, 2), nullable=False)
    project_category = db.Column(db.String(50), nullable=True)
    applies_on = db.Column(db.String(20), default='amount_raised')
    
    min_amount = db.Column(db.Numeric(12, 2), default=0)
    max_amount = db.Column(db.Numeric(12, 2), nullable=True)
    
    fixed_fee = db.Column(db.Numeric(10, 2), default=0)
    fixed_fee_currency = db.Column(db.String(3), default='HTG')
    
    min_amount_to_apply = db.Column(db.Numeric(12, 2), default=0)
    
    valid_from = db.Column(db.DateTime, default=utc_now)
    valid_until = db.Column(db.DateTime, nullable=True)
    
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)
    
    description_fr = db.Column(db.Text, nullable=True)
    description_ht = db.Column(db.Text, nullable=True)
    description_en = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    __table_args__ = (
        CheckConstraint('percentage >= 0 AND percentage <= 20', name='check_valid_percentage'),
        CheckConstraint('fixed_fee >= 0', name='check_positive_fixed_fee'),
        Index('idx_commission_config_active', 'is_active', 'valid_from'),
        Index('idx_commission_config_type', 'commission_type', 'is_active'),
    )
    
    def calculate_commission(self, amount):
        # Les defaults de colonnes ne s'appliquent qu'à l'INSERT : une config non persistée
        # (repli quand la table est vide) a ces champs à None.
        amount = Decimal(str(amount))
        if amount < (self.min_amount_to_apply or 0):
            return Decimal(0)
        
        percentage_commission = (amount * self.percentage) / Decimal(100)
        fixed_commission = self.fixed_fee or Decimal(0)
        total_commission = percentage_commission + fixed_commission
        
        if self.max_amount and amount > self.max_amount:
            total_commission = total_commission * Decimal('0.5')

        total_commission = total_commission.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        total_commission = total_commission.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        return total_commission
    
    def to_dict(self):
        return {
            'id': self.id,
            'commission_type': self.commission_type,
            'percentage': float(self.percentage),
            'fixed_fee': float(self.fixed_fee),
            'min_amount_to_apply': float(self.min_amount_to_apply),
            'description_fr': self.description_fr,
            'description_ht': self.description_ht,
            'is_active': self.is_active,
            'is_default': self.is_default,
        }


class PlatformEarning(db.Model):
    __tablename__ = 'platform_earnings'

    id = db.Column(db.Integer, primary_key=True)
    
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='SET NULL'), 
                           nullable=True, index=True)
    contribution_id = db.Column(db.Integer, db.ForeignKey('contributions.id', ondelete='SET NULL'),
                                nullable=True, index=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    
    earning_type = db.Column(db.String(30), nullable=False)
    
    amount_original = db.Column(db.Numeric(12, 2), nullable=False)
    amount_currency = db.Column(db.String(3), nullable=False, default='HTG')
    
    commission_percentage = db.Column(db.Numeric(5, 2), nullable=False)
    commission_amount = db.Column(db.Numeric(12, 2), nullable=False)
    fixed_fee_amount = db.Column(db.Numeric(10, 2), default=0)
    
    commission_amount_htg = db.Column(db.Numeric(12, 2), nullable=False)
    exchange_rate = db.Column(db.Numeric(12, 6), nullable=True)
    
    net_to_project = db.Column(db.Numeric(12, 2), nullable=False)
    
    status = db.Column(db.String(20), default='pending')
    
    paid_to_ceo = db.Column(db.Boolean, default=False)
    paid_at = db.Column(db.DateTime, nullable=True)
    payout_reference = db.Column(db.String(100), nullable=True)
    
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    project = db.relationship('Project', foreign_keys=[project_id])
    
    __table_args__ = (
        CheckConstraint('commission_amount >= 0', name='check_positive_commission'),
        Index('idx_earnings_project_status', 'project_id', 'status'),
        Index('idx_earnings_paid_status', 'paid_to_ceo', 'status'),
        Index('idx_earnings_type_created', 'earning_type', 'created_at'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'project_title': self.project.title if self.project else None,
            'earning_type': self.earning_type,
            'commission_percentage': float(self.commission_percentage),
            'commission_amount': float(self.commission_amount),
            'commission_amount_htg': float(self.commission_amount_htg),
            'net_to_project': float(self.net_to_project),
            'status': self.status,
            'paid_to_ceo': self.paid_to_ceo,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class CEOPayout(db.Model):
    __tablename__ = 'ceo_payouts'

    id = db.Column(db.Integer, primary_key=True)
    
    payout_reference = db.Column(db.String(100), unique=True, nullable=False)
    
    period_start = db.Column(db.DateTime, nullable=False)
    period_end = db.Column(db.DateTime, nullable=False)
    
    total_earnings = db.Column(db.Numeric(12, 2), nullable=False)
    total_earnings_htg = db.Column(db.Numeric(12, 2), nullable=False)
    
    earnings_ids = db.Column(db.Text, nullable=True)
    projects_breakdown = db.Column(db.Text, nullable=True)
    
    payout_method = db.Column(db.String(30), default='bank_transfer')
    payout_account = db.Column(db.String(100), nullable=True)
    payout_amount = db.Column(db.Numeric(12, 2), nullable=False)
    payout_currency = db.Column(db.String(3), default='USD')
    
    transfer_fee = db.Column(db.Numeric(10, 2), default=0)
    net_received = db.Column(db.Numeric(12, 2), nullable=False)
    
    status = db.Column(db.String(20), default='pending')
    
    transaction_id = db.Column(db.String(100), nullable=True)
    external_reference = db.Column(db.String(100), nullable=True)
    
    initiated_at = db.Column(db.DateTime, default=utc_now)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    __table_args__ = (
        Index('idx_ceo_payouts_status', 'status', 'initiated_at'),
        Index('idx_ceo_payouts_period', 'period_start', 'period_end'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'payout_reference': self.payout_reference,
            'period_start': self.period_start.isoformat() if self.period_start else None,
            'period_end': self.period_end.isoformat() if self.period_end else None,
            'total_earnings': float(self.total_earnings),
            'total_earnings_htg': float(self.total_earnings_htg),
            'payout_amount': float(self.payout_amount),
            'payout_currency': self.payout_currency,
            'status': self.status,
            'initiated_at': self.initiated_at.isoformat() if self.initiated_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class CommissionAuditLog(db.Model):
    __tablename__ = 'commission_audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    
    action = db.Column(db.String(50), nullable=False)
    config_id = db.Column(db.Integer, nullable=False)
    old_percentage = db.Column(db.Numeric(5, 2), nullable=True)
    new_percentage = db.Column(db.Numeric(5, 2), nullable=True)
    changed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    changed_at = db.Column(db.DateTime, default=utc_now)
    reason = db.Column(db.Text, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'action': self.action,
            'config_id': self.config_id,
            'old_percentage': float(self.old_percentage) if self.old_percentage else None,
            'new_percentage': float(self.new_percentage) if self.new_percentage else None,
            'changed_by': self.changed_by.name if self.changed_by else None,
            'changed_at': self.changed_at.isoformat() if self.changed_at else None,
            'reason': self.reason,
        }