"""
Modèle pour les mises à jour des récoltes et projets
"""

from datetime import datetime, timezone
from sqlalchemy import Index
from app.extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class HarvestUpdate(db.Model):
    __tablename__ = 'harvest_updates'

    id = db.Column(db.Integer, primary_key=True)
    
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    
    title = db.Column(db.String(200), nullable=False)
    title_ht = db.Column(db.String(200), nullable=True)
    content = db.Column(db.Text, nullable=False)
    content_ht = db.Column(db.Text, nullable=True)
    
    update_type = db.Column(db.String(20), default='general')
    
    image_url = db.Column(db.String(200), nullable=True)
    video_url = db.Column(db.String(200), nullable=True)
    
    is_important = db.Column(db.Boolean, default=False)
    is_published = db.Column(db.Boolean, default=True)
    
    notify_investors = db.Column(db.Boolean, default=False)
    notification_sent_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        Index('idx_harvest_updates_project_important', 'project_id', 'is_important'),
        Index('idx_harvest_updates_created', 'created_at', 'project_id'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'title': self.title,
            'title_ht': self.title_ht,
            'content': self.content,
            'update_type': self.update_type,
            'image_url': self.image_url,
            'video_url': self.video_url,
            'is_important': self.is_important,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<HarvestUpdate {self.title}>'