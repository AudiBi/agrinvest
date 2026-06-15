"""
Modèles pour les formations en ligne des agriculteurs
"""

from datetime import datetime, timezone
from sqlalchemy import Index, UniqueConstraint
from app.extensions import db
from app.models.enums import TrainingType


def utc_now():
    return datetime.now(timezone.utc)


class Training(db.Model):
    __tablename__ = 'trainings'

    id = db.Column(db.Integer, primary_key=True)
    
    title_ht = db.Column(db.String(200), nullable=False)
    title_fr = db.Column(db.String(200), nullable=True)
    title_en = db.Column(db.String(200), nullable=True)
    
    description_ht = db.Column(db.Text, nullable=False)
    description_fr = db.Column(db.Text, nullable=True)
    description_en = db.Column(db.Text, nullable=True)
    
    content_type = db.Column(db.String(20), nullable=False)
    content_url = db.Column(db.String(500), nullable=False)
    thumbnail_url = db.Column(db.String(200), nullable=True)
    file_size_mb = db.Column(db.Float, nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=True)
    
    content_url_light = db.Column(db.String(500), nullable=True)
    audio_only_url = db.Column(db.String(500), nullable=True)
    
    is_downloadable = db.Column(db.Boolean, default=True)
    whatsapp_forwardable = db.Column(db.Boolean, default=True)
    
    category = db.Column(db.String(50), nullable=False, index=True)
    difficulty_level = db.Column(db.String(20), default='beginner')
    
    region_specific = db.Column(db.String(50), nullable=True, index=True)
    
    sort_order = db.Column(db.Integer, default=0)
    
    is_published = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    progress = db.relationship('TrainingProgress', backref='training', lazy='dynamic')

    __table_args__ = (
        Index('idx_trainings_category_published', 'category', 'is_published'),
        Index('idx_trainings_region_published', 'region_specific', 'is_published'),
        Index('idx_trainings_featured', 'is_featured', 'sort_order'),
    )
    
    def to_dict(self, language='ht'):
        title_field = f'title_{language}' if language in ['ht', 'fr', 'en'] else 'title_ht'
        desc_field = f'description_{language}' if language in ['ht', 'fr', 'en'] else 'description_ht'
        
        return {
            'id': self.id,
            'title': getattr(self, title_field, self.title_ht),
            'description': getattr(self, desc_field, self.description_ht),
            'content_type': self.content_type,
            'content_url': self.content_url,
            'content_url_light': self.content_url_light,
            'audio_only_url': self.audio_only_url,
            'thumbnail_url': self.thumbnail_url,
            'duration_minutes': self.duration_minutes,
            'file_size_mb': self.file_size_mb,
            'category': self.category,
            'difficulty_level': self.difficulty_level,
            'is_downloadable': self.is_downloadable,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class TrainingProgress(db.Model):
    __tablename__ = 'training_progress'

    id = db.Column(db.Integer, primary_key=True)
    
    farmer_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'),
                          nullable=False, index=True)
    training_id = db.Column(db.Integer, db.ForeignKey('trainings.id', ondelete='CASCADE'),
                            nullable=False, index=True)
    
    status = db.Column(db.String(20), default='started')
    progress_percentage = db.Column(db.Integer, default=0)
    last_position_seconds = db.Column(db.Integer, default=0)
    
    completed_at = db.Column(db.DateTime, nullable=True)
    
    certificate_generated = db.Column(db.Boolean, default=False)
    certificate_url = db.Column(db.String(200), nullable=True)
    
    device_info = db.Column(db.String(200), nullable=True)
    last_accessed_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    started_at = db.Column(db.DateTime, default=utc_now)
    
    __table_args__ = (
        UniqueConstraint('farmer_id', 'training_id', name='uq_farmer_training'),
        Index('idx_training_progress_status', 'status', 'progress_percentage'),
    )
    
    def mark_completed(self):
        self.status = 'completed'
        self.progress_percentage = 100
        self.completed_at = utc_now()
        db.session.commit()
    
    def update_progress(self, seconds):
        if self.training and self.training.duration_minutes:
            total_seconds = self.training.duration_minutes * 60
            self.progress_percentage = min(100, int((seconds / total_seconds) * 100))
        self.last_position_seconds = seconds
        self.last_accessed_at = utc_now()
        db.session.commit()
    
    def to_dict(self):
        return {
            'id': self.id,
            'training_id': self.training_id,
            'training_title': self.training.title_ht if self.training else None,
            'status': self.status,
            'progress_percentage': self.progress_percentage,
            'last_position_seconds': self.last_position_seconds,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'certificate_url': self.certificate_url,
        }