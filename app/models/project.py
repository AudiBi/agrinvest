"""
Modèle Projet Agricole
"""

from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Index, CheckConstraint
from app.extensions import db
from app.models.enums import ProjectStatus


def utc_now():
    return datetime.now(timezone.utc)


def generate_slug(title, model, slug_field='slug'):
    import re
    slug = re.sub(r'[^\w\s-]', '', title.lower())
    slug = re.sub(r'[-\s]+', '-', slug).strip('-')
    
    base_slug = slug
    counter = 1
    while db.session.query(model).filter(getattr(model, slug_field) == slug).first():
        slug = f'{base_slug}-{counter}'
        counter += 1
    return slug


class Project(db.Model):
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    
    # Identité
    title = db.Column(db.String(200), nullable=False, index=True)
    title_ht = db.Column(db.String(200), nullable=True)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    
    # Descriptions
    description = db.Column(db.Text, nullable=False)
    description_ht = db.Column(db.Text, nullable=True)
    short_description = db.Column(db.String(300), nullable=True)
    short_description_ht = db.Column(db.String(300), nullable=True)
    
    # Localisation
    location = db.Column(db.String(100), nullable=True)
    department = db.Column(db.String(50), nullable=True, index=True)
    commune = db.Column(db.String(50), nullable=True)
    village = db.Column(db.String(50), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    
    # Catégorisation
    category = db.Column(db.String(50), nullable=True, index=True)
    subcategory = db.Column(db.String(50), nullable=True)
    
    # Médias
    image_url = db.Column(db.String(200), nullable=True)
    video_url = db.Column(db.String(200), nullable=True)
    gallery_images = db.Column(db.Text, nullable=True)
    
    # Financement
    amount_needed = db.Column(db.Numeric(12, 2), nullable=False)
    amount_raised = db.Column(db.Numeric(12, 2), default=0)
    min_investment = db.Column(db.Numeric(10, 2), default=Decimal('10.00'))
    max_investment = db.Column(db.Numeric(12, 2), nullable=True)
    currency = db.Column(db.String(3), default='HTG')
    
    # Calendrier
    deadline = db.Column(db.DateTime, nullable=True, index=True)
    published_at = db.Column(db.DateTime, nullable=True)
    
    # Statut
    status = db.Column(db.String(20), nullable=False, default=ProjectStatus.DRAFT, index=True)
    is_featured = db.Column(db.Boolean, default=False, index=True)
    is_published = db.Column(db.Boolean, default=False, index=True)
    is_verified = db.Column(db.Boolean, default=False)
    
    # Impact
    estimated_jobs = db.Column(db.Integer, default=0)
    estimated_farmers_helped = db.Column(db.Integer, default=0)
    co2_reduction_kg = db.Column(db.Numeric(10, 2), default=0)
    
    # Commission
    applied_commission_percentage = db.Column(db.Numeric(5, 2), nullable=True)
    estimated_platform_fee = db.Column(db.Numeric(12, 2), nullable=True)
    actual_platform_fee = db.Column(db.Numeric(12, 2), default=0)
    net_amount_to_farmer = db.Column(db.Numeric(12, 2), nullable=True)
    commission_charged = db.Column(db.Boolean, default=False)
    commission_charged_at = db.Column(db.DateTime, nullable=True)
    
    # Clés étrangères
    farmer_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='RESTRICT'), 
                          nullable=False, index=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relations
    contributions = db.relationship('Contribution', backref='project', lazy='dynamic', cascade='all, delete-orphan')
    updates = db.relationship('HarvestUpdate', backref='project', lazy='dynamic', cascade='all, delete-orphan')
    diaspora_campaigns = db.relationship('DiasporaCampaign', backref='project', lazy='dynamic', cascade='all, delete-orphan')
    collection_points = db.relationship('ProjectCollectionPoint', backref='project', lazy='dynamic')

    __table_args__ = (
        CheckConstraint('amount_needed > 0', name='check_positive_needed'),
        CheckConstraint('min_investment > 0', name='check_positive_min_investment'),
        Index('idx_projects_status_deadline', 'status', 'deadline'),
        Index('idx_projects_category_status', 'category', 'status'),
        Index('idx_projects_department_status', 'department', 'status'),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.slug and 'title' in kwargs:
            self.slug = generate_slug(kwargs['title'], Project)

    @property
    def progress_percentage(self):
        if self.amount_needed and self.amount_needed > 0:
            return min(100, round(float(self.amount_raised / self.amount_needed) * 100, 1))
        return 0

    @property
    def is_funded(self):
        return self.amount_raised >= self.amount_needed

    @property
    def is_expired(self):
        if self.deadline:
            return utc_now() > self.deadline
        return False

    @property
    def days_remaining(self):
        if self.deadline:
            delta = self.deadline - utc_now()
            return max(0, delta.days)
        return None

    @property
    def investor_count(self):
        from app.models.contribution import Contribution, ContributionStatus
        return self.contributions.filter_by(status=ContributionStatus.COMPLETED).count()

    @property
    def diaspora_investor_count(self):
        from app.models.contribution import Contribution, ContributionStatus
        from app.models.user import User
        return self.contributions.join(User)\
            .filter(Contribution.status == ContributionStatus.COMPLETED,
                    User.country != 'HT')\
            .count()

    @property
    def days_remaining(self):
        if self.deadline:
            # S'assurer que deadline est offset-aware
            if self.deadline.tzinfo is None:
                from datetime import timezone
                deadline = self.deadline.replace(tzinfo=timezone.utc)
            else:
                deadline = self.deadline
            
            now = utc_now()
            delta = deadline - now
            return max(0, delta.days)
        return None

    @property
    def is_expired(self):
        if self.deadline:
            # S'assurer que deadline est offset-aware
            if self.deadline.tzinfo is None:
                deadline = self.deadline.replace(tzinfo=timezone.utc)
            else:
                deadline = self.deadline
            return utc_now() > deadline
        return False

    @property
    def days_remaining(self):
        if self.deadline:
            # S'assurer que deadline est offset-aware
            if self.deadline.tzinfo is None:
                deadline = self.deadline.replace(tzinfo=timezone.utc)
            else:
                deadline = self.deadline
            
            now = utc_now()
            delta = deadline - now
            return max(0, delta.days)
        return None

    def can_accept_contribution(self, amount):
        if self.is_expired:
            return False, "Le projet a dépassé sa date limite"
        if amount < self.min_investment:
            return False, f"L'investissement minimum est de {self.min_investment} {self.currency}"
        if self.max_investment and amount > self.max_investment:
            return False, f"L'investissement maximum est de {self.max_investment} {self.currency}"
        if self.is_funded:
            return False, "Le projet est déjà entièrement financé"
        return True, "OK"

    def add_contribution(self, amount):
        self.amount_raised += Decimal(str(amount))
        if self.is_funded:
            self.status = ProjectStatus.FUNDED
        db.session.commit()

    def submit_for_publication(self):
        """Publie le projet, ou le place en file de modération si REQUIRE_PROJECT_APPROVAL est actif.

        Retourne True si le projet est publié, False s'il attend la validation d'un administrateur.
        """
        from flask import current_app
        if current_app.config.get('REQUIRE_PROJECT_APPROVAL'):
            self.status = ProjectStatus.PENDING
            self.is_published = False
            db.session.commit()
            return False
        self.publish()
        return True

    def publish(self):
        self.is_published = True
        self.status = ProjectStatus.PUBLISHED
        self.published_at = utc_now()
        db.session.commit()

    def get_commission_config(self):
        from app.models.platform_commission import PlatformCommissionConfig
        config = PlatformCommissionConfig.query.filter(
            PlatformCommissionConfig.is_active == True,
            PlatformCommissionConfig.valid_from <= utc_now(),
            (PlatformCommissionConfig.valid_until.is_(None) | 
             (PlatformCommissionConfig.valid_until >= utc_now())),
            (PlatformCommissionConfig.project_category.is_(None) | 
             (PlatformCommissionConfig.project_category == self.category))
        ).order_by(
            PlatformCommissionConfig.project_category.is_(None).asc(),  # catégorie du projet d'abord
            PlatformCommissionConfig.is_default.desc()
        ).first()
        
        if not config:
            from app.models.platform_commission import PlatformCommissionConfig
            config = PlatformCommissionConfig(
                percentage=Decimal('3.0'),
                commission_type='platform_fee',
                is_default=True,
                min_amount_to_apply=Decimal('0'),
                fixed_fee=Decimal('0'),
            )
        return config

    def get_featured_image(self):
        if self.image_url:
            return self.image_url
        return '/static/images/project-default.jpg'

    def to_dict(self, include_updates=False):
        data = {
            'id': self.id,
            'title': self.title,
            'title_ht': self.title_ht,
            'slug': self.slug,
            'description': self.description,
            'short_description': self.short_description,
            'location': self.location,
            'department': self.department,
            'category': self.category,
            'image_url': self.image_url,
            'video_url': self.video_url,
            'amount_needed': float(self.amount_needed) if self.amount_needed else 0,
            'amount_raised': float(self.amount_raised) if self.amount_raised else 0,
            'min_investment': float(self.min_investment) if self.min_investment else 0,
            'currency': self.currency,
            'progress': self.progress_percentage,
            'status': self.status,
            'is_funded': self.is_funded,
            'is_expired': self.is_expired,
            'days_remaining': self.days_remaining,
            'investor_count': self.investor_count,
            'diaspora_investor_count': self.diaspora_investor_count,
            'farmer_id': self.farmer_id,
            'farmer_name': self.farmer.name if self.farmer else None,
            'commission_percentage': float(self.applied_commission_percentage) if self.applied_commission_percentage else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'deadline': self.deadline.isoformat() if self.deadline else None,
        }
        if include_updates:
            data['updates'] = [u.to_dict() for u in self.updates.limit(5).all()]
        return data

    def __repr__(self):
        return f'<Project {self.title}>'