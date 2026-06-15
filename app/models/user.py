"""
Modèle Utilisateur (Investisseurs, Agriculteurs, Ambassadeurs, Agents)
"""

from datetime import datetime, timezone
from decimal import Decimal
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Index, CheckConstraint
from app.extensions import db, login_manager
from app.models.enums import UserRole


def utc_now():
    return datetime.now(timezone.utc)


class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    
    # Identité
    role = db.Column(db.String(20), nullable=False, default=UserRole.INVESTOR, index=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    
    # Contact
    phone = db.Column(db.String(20), nullable=True, index=True)
    alternative_phone = db.Column(db.String(20), nullable=True)
    location = db.Column(db.String(100), nullable=True)
    
    # Profil
    bio = db.Column(db.Text, nullable=True)
    avatar_url = db.Column(db.String(200), nullable=True)
    
    # Localisation géographique
    country = db.Column(db.String(2), nullable=True, index=True)
    city = db.Column(db.String(100), nullable=True)
    department = db.Column(db.String(50), nullable=True)
    commune = db.Column(db.String(50), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    
    # Diaspora
    diaspora_community = db.Column(db.String(50), nullable=True)
    hometown_in_haiti = db.Column(db.String(50), nullable=True)
    
    # Préférences
    preferred_currency = db.Column(db.String(3), default='USD')
    preferred_language = db.Column(db.String(10), default='ht')
    
    # Statut
    is_verified = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    email_verified_at = db.Column(db.DateTime, nullable=True)
    phone_verified_at = db.Column(db.DateTime, nullable=True)
    
    # Fiscalité
    tax_receipt_eligible = db.Column(db.Boolean, default=False)
    tax_id = db.Column(db.String(50), nullable=True)
    tax_address = db.Column(db.String(200), nullable=True)
    
    # Marketing
    diaspora_newsletter = db.Column(db.Boolean, default=False)
    sms_alerts_enabled = db.Column(db.Boolean, default=True)
    whatsapp_alerts_enabled = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    last_login_at = db.Column(db.DateTime, nullable=True)
    
    # Relations (string references pour éviter circular imports)
    projects = db.relationship('Project', backref='farmer', lazy='dynamic', cascade='all, delete-orphan')
    contributions = db.relationship('Contribution', foreign_keys='Contribution.investor_id', 
                                    backref='investor', lazy='dynamic', cascade='all, delete-orphan')
    sent_invites = db.relationship('GroupContributionInvite', foreign_keys='GroupContributionInvite.invited_by_id',
                                   backref='inviter', lazy='dynamic')
    ambassador_campaigns = db.relationship('DiasporaCampaign', foreign_keys='DiasporaCampaign.ambassador_id',
                                           backref='ambassador', lazy='dynamic')
    training_progress = db.relationship('TrainingProgress', backref='farmer', lazy='dynamic')
    weather_subscriptions = db.relationship('WeatherSubscription', backref='subscriber', lazy='dynamic')

    __table_args__ = (
        Index('idx_users_role_country', 'role', 'country'),
        Index('idx_users_created_role', 'created_at', 'role'),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if 'password' in kwargs:
            self.set_password(kwargs['password'])

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def password(self):
        raise AttributeError('Le mot de passe est en écriture seule.')

    @password.setter
    def password(self, password):
        self.set_password(password)

    @property
    def is_farmer(self):
        return self.role == UserRole.FARMER

    @property
    def is_investor(self):
        return self.role == UserRole.INVESTOR

    @property
    def is_agent(self):
        return self.role == UserRole.AGENT

    @property
    def is_ambassador(self):
        return self.role == UserRole.AMBASSADOR

    @property
    def is_diaspora(self):
        return self.country and self.country != 'HT'

    def get_id(self):
        return str(self.id)

    def verify_email(self):
        self.email_verified_at = utc_now()
        self.is_verified = True
        db.session.commit()

    def update_profile(self, **kwargs):
        allowed_fields = ['name', 'phone', 'location', 'bio', 'avatar_url', 
                          'country', 'city', 'preferred_currency', 'preferred_language',
                          'diaspora_newsletter', 'sms_alerts_enabled', 'whatsapp_alerts_enabled']
        for key, value in kwargs.items():
            if key in allowed_fields and hasattr(self, key):
                setattr(self, key, value)
        db.session.commit()

    def get_total_invested(self):
        from app.models.contribution import Contribution, ContributionStatus
        total = db.session.query(db.func.sum(Contribution.amount_htg))\
            .filter(Contribution.investor_id == self.id,
                    Contribution.status == ContributionStatus.COMPLETED)\
            .scalar() or Decimal(0)
        return total

    def to_dict(self, include_email=False):
        data = {
            'id': self.id,
            'role': self.role,
            'name': self.name,
            'phone': self.phone,
            'location': self.location,
            'bio': self.bio,
            'avatar_url': self.avatar_url,
            'country': self.country,
            'city': self.city,
            'is_verified': self.is_verified,
            'is_diaspora': self.is_diaspora,
            'preferred_currency': self.preferred_currency,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if include_email:
            data['email'] = self.email
        return data

    def __repr__(self):
        return f'<User {self.name} ({self.role})>'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))