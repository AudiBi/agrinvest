"""
Modèle Contribution (Investissement)
"""

from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Index, CheckConstraint
from app.extensions import db
from app.models.enums import ContributionStatus


def utc_now():
    return datetime.now(timezone.utc)


class Contribution(db.Model):
    __tablename__ = 'contributions'

    id = db.Column(db.Integer, primary_key=True)
    
    # Liens
    investor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='RESTRICT'),
                            nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='RESTRICT'),
                           nullable=False, index=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group_contributions.id'), nullable=True)
    
    # Montants en devise d'origine
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default='USD')
    
    # Conversion vers gourdes (HTG)
    amount_htg = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    exchange_rate = db.Column(db.Numeric(12, 6), nullable=True)
    exchange_rate_date = db.Column(db.DateTime, nullable=True)
    
    # Montant converti pour affichage
    amount_converted = db.Column(db.Numeric(12, 2), nullable=True)
    converted_currency = db.Column(db.String(3), nullable=True)
    
    # Frais (avec valeurs par défaut)
    gateway_fee = db.Column(db.Numeric(10, 2), default=Decimal('0'), nullable=False)
    gateway_fee_currency = db.Column(db.String(3), nullable=True)
    conversion_fee = db.Column(db.Numeric(10, 2), default=Decimal('0'), nullable=False)
    platform_fee = db.Column(db.Numeric(10, 2), default=Decimal('0'), nullable=False)
    net_amount_htg = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    
    # Commission plateforme
    platform_commission_applied = db.Column(db.Numeric(5, 2), nullable=True)
    platform_commission_amount = db.Column(db.Numeric(12, 2), default=Decimal('0'), nullable=False)
    
    # Paiement
    payment_method = db.Column(db.String(30), nullable=False)
    payment_gateway = db.Column(db.String(30), nullable=True)
    
    # Identifiants de paiement
    stripe_payment_intent_id = db.Column(db.String(100), unique=True, nullable=True)
    stripe_payment_method_id = db.Column(db.String(100), nullable=True)
    paypal_order_id = db.Column(db.String(100), unique=True, nullable=True)
    paypal_payer_id = db.Column(db.String(100), nullable=True)
    moncash_payment_id = db.Column(db.String(100), unique=True, nullable=True)
    moncash_transaction_id = db.Column(db.String(100), nullable=True)
    interac_reference = db.Column(db.String(100), unique=True, nullable=True)
    lydia_payment_id = db.Column(db.String(100), unique=True, nullable=True)
    cash_receipt_number = db.Column(db.String(50), nullable=True)
    collection_point_id = db.Column(db.Integer, db.ForeignKey('collection_points.id'), nullable=True)
    
    # Informations géographiques
    investor_country = db.Column(db.String(2), nullable=True, index=True)
    investor_ip = db.Column(db.String(45), nullable=True)
    
    # Statut
    status = db.Column(db.String(20), nullable=False, default=ContributionStatus.PENDING, index=True)
    
    # Anonymat
    is_anonymous = db.Column(db.Boolean, default=False)
    message = db.Column(db.Text, nullable=True)
    public_message = db.Column(db.Text, nullable=True)
    
    # Reçus fiscaux
    tax_receipt_issued = db.Column(db.Boolean, default=False)
    tax_receipt_number = db.Column(db.String(50), nullable=True)
    tax_receipt_issued_at = db.Column(db.DateTime, nullable=True)
    
    # Transfert
    transfer_batch_id = db.Column(db.String(50), nullable=True, index=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    refunded_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        CheckConstraint('amount > 0', name='check_positive_amount'),
        Index('idx_contributions_investor_status', 'investor_id', 'status'),
        Index('idx_contributions_project_status', 'project_id', 'status'),
        Index('idx_contributions_created_status', 'created_at', 'status'),
        Index('idx_contributions_country_status', 'investor_country', 'status'),
    )

    def __init__(self, **kwargs):
        # Extraire et définir les valeurs par défaut pour Decimal
        gateway_fee = kwargs.pop('gateway_fee', Decimal('0'))
        if gateway_fee is None:
            gateway_fee = Decimal('0')
        elif not isinstance(gateway_fee, Decimal):
            gateway_fee = Decimal(str(gateway_fee))
        
        conversion_fee = kwargs.pop('conversion_fee', Decimal('0'))
        if conversion_fee is None:
            conversion_fee = Decimal('0')
        elif not isinstance(conversion_fee, Decimal):
            conversion_fee = Decimal(str(conversion_fee))
        
        platform_fee = kwargs.pop('platform_fee', Decimal('0'))
        if platform_fee is None:
            platform_fee = Decimal('0')
        elif not isinstance(platform_fee, Decimal):
            platform_fee = Decimal(str(platform_fee))
        
        platform_commission_amount = kwargs.pop('platform_commission_amount', Decimal('0'))
        if platform_commission_amount is None:
            platform_commission_amount = Decimal('0')
        elif not isinstance(platform_commission_amount, Decimal):
            platform_commission_amount = Decimal(str(platform_commission_amount))
        
        amount_htg = kwargs.get('amount_htg', Decimal('0'))
        if amount_htg is None:
            amount_htg = Decimal('0')
        elif not isinstance(amount_htg, Decimal):
            amount_htg = Decimal(str(amount_htg))
        
        # Appeler le constructeur parent
        super().__init__(**kwargs)
        
        # Assigner les valeurs
        self.gateway_fee = gateway_fee
        self.conversion_fee = conversion_fee
        self.platform_fee = platform_fee
        self.platform_commission_amount = platform_commission_amount
        self.amount_htg = amount_htg
        
        # Calculer net_amount_htg
        self.net_amount_htg = (self.amount_htg - self.gateway_fee - 
                               self.conversion_fee - self.platform_fee -
                               self.platform_commission_amount)

    @property
    def display_amount(self):
        return f'{self.amount:,.2f} {self.currency}'

    @property
    def is_from_diaspora(self):
        return self.investor_country and self.investor_country != 'HT'

    def mark_completed(self):
        from app.models.platform_commission import PlatformEarning
        
        self.status = ContributionStatus.COMPLETED
        self.completed_at = utc_now()
        
        # Calculer et appliquer la commission plateforme
        if self.project and not self.platform_commission_applied:
            config = self.project.get_commission_config()
            self.platform_commission_applied = config.percentage
            self.platform_commission_amount = config.calculate_commission(self.amount_htg)
            
            # Créer l'enregistrement de gain
            earning = PlatformEarning(
                project_id=self.project_id,
                contribution_id=self.id,
                farmer_id=self.project.farmer_id,
                earning_type='platform_fee',
                amount_original=self.amount_htg,
                amount_currency='HTG',
                commission_percentage=config.percentage,
                commission_amount=self.platform_commission_amount,
                net_to_project=self.amount_htg - self.platform_commission_amount
            )
            db.session.add(earning)
            
            # Recalculer net_amount_htg
            self.net_amount_htg = self.amount_htg - self.platform_commission_amount - self.gateway_fee - self.conversion_fee - self.platform_fee
        
        self.project.add_contribution(self.amount_htg)
        db.session.commit()

    def mark_failed(self):
        self.status = ContributionStatus.FAILED
        db.session.commit()

    def mark_refunded(self):
        self.status = ContributionStatus.REFUNDED
        self.refunded_at = utc_now()
        if self.project and self.amount_htg:
            self.project.amount_raised -= self.amount_htg
            db.session.commit()

    def to_dict(self):
        return {
            'id': self.id,
            'investor_id': self.investor_id,
            'investor_name': self.investor.name if self.investor and not self.is_anonymous else 'Anonyme',
            'investor_country': self.investor_country,
            'project_id': self.project_id,
            'project_title': self.project.title if self.project else None,
            'amount': float(self.amount),
            'amount_htg': float(self.amount_htg),
            'currency': self.currency,
            'status': self.status,
            'is_anonymous': self.is_anonymous,
            'message': self.message if not self.is_anonymous else None,
            'is_from_diaspora': self.is_from_diaspora,
            'commission_applied': float(self.platform_commission_applied) if self.platform_commission_applied else 0,
            'commission_amount': float(self.platform_commission_amount) if self.platform_commission_amount else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }

    def __repr__(self):
        return f'<Contribution {self.amount} {self.currency} by User {self.investor_id}>'