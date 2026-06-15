"""
Modèles pour les cagnottes de groupe (famille, église, association)
"""

from datetime import datetime, timezone
from decimal import Decimal
import secrets
from sqlalchemy import Index, CheckConstraint
from app.extensions import db
from app.models.enums import ContributionStatus


def utc_now():
    return datetime.now(timezone.utc)


class GroupContribution(db.Model):
    __tablename__ = 'group_contributions'

    id = db.Column(db.Integer, primary_key=True)
    
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'),
                          nullable=False, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='RESTRICT'),
                              nullable=False, index=True)
    
    group_name = db.Column(db.String(100), nullable=False)
    group_name_ht = db.Column(db.String(100), nullable=True)
    group_type = db.Column(db.String(30), nullable=False)
    group_description = db.Column(db.Text, nullable=True)
    
    target_amount = db.Column(db.Numeric(12, 2), nullable=False)
    current_amount = db.Column(db.Numeric(12, 2), default=0)
    currency = db.Column(db.String(3), default='USD')
    
    shareable_link = db.Column(db.String(100), unique=True, nullable=False)
    qr_code_url = db.Column(db.String(200), nullable=True)
    
    expires_at = db.Column(db.DateTime, nullable=True)
    max_members = db.Column(db.Integer, nullable=True)
    is_public = db.Column(db.Boolean, default=True)
    
    cover_image_url = db.Column(db.String(200), nullable=True)
    
    status = db.Column(db.String(20), default='active')
    
    created_at = db.Column(db.DateTime, default=utc_now)
    completed_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    contributions = db.relationship('Contribution', backref='group', lazy='dynamic')
    invites = db.relationship('GroupContributionInvite', backref='group', 
                              lazy='dynamic', cascade='all, delete-orphan')

    __table_args__ = (
        CheckConstraint('target_amount > 0', name='check_positive_target'),
        Index('idx_group_contributions_project', 'project_id', 'status'),
        Index('idx_group_contributions_created', 'created_by_id', 'status'),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.shareable_link:
            self.shareable_link = secrets.token_urlsafe(16)

    @property
    def progress_percentage(self):
        if self.target_amount > 0:
            return min(100, round(float(self.current_amount / self.target_amount) * 100, 1))
        return 0

    @property
    def member_count(self):
        return self.contributions.filter_by(status=ContributionStatus.COMPLETED).distinct('investor_id').count()

    def add_contribution(self, amount):
        self.current_amount += Decimal(str(amount))
        if self.current_amount >= self.target_amount:
            self.status = 'completed'
            self.completed_at = utc_now()
        db.session.commit()

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'project_title': self.project.title if self.project else None,
            'group_name': self.group_name,
            'group_type': self.group_type,
            'target_amount': float(self.target_amount),
            'current_amount': float(self.current_amount),
            'progress': self.progress_percentage,
            'member_count': self.member_count,
            'shareable_link': self.shareable_link,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class GroupContributionInvite(db.Model):
    __tablename__ = 'group_contribution_invites'

    id = db.Column(db.Integer, primary_key=True)
    
    group_id = db.Column(db.Integer, db.ForeignKey('group_contributions.id', ondelete='CASCADE'),
                         nullable=False, index=True)
    invited_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='RESTRICT'),
                              nullable=False, index=True)
    
    invite_email = db.Column(db.String(120), nullable=True)
    invite_phone = db.Column(db.String(20), nullable=True)
    invite_code = db.Column(db.String(50), unique=True, nullable=False)
    
    personal_message = db.Column(db.Text, nullable=True)
    
    status = db.Column(db.String(20), default='pending')
    
    sent_at = db.Column(db.DateTime, default=utc_now)
    responded_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.invite_code:
            self.invite_code = secrets.token_urlsafe(12)
        if not self.expires_at:
            self.expires_at = utc_now().replace(day=utc_now().day + 7)

    def to_dict(self):
        return {
            'id': self.id,
            'group_id': self.group_id,
            'invite_email': self.invite_email,
            'invite_phone': self.invite_phone,
            'invite_code': self.invite_code,
            'personal_message': self.personal_message,
            'status': self.status,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
        }