"""
Modèle pour l'analytique et le suivi utilisateur
"""

from datetime import datetime, timezone
from sqlalchemy import Index
from app.extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class AnalyticsEvent(db.Model):
    __tablename__ = 'analytics_events'

    id = db.Column(db.Integer, primary_key=True)
    
    event_type = db.Column(db.String(50), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    
    page_url = db.Column(db.String(500), nullable=True)
    referrer = db.Column(db.String(500), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    
    event_data = db.Column(db.Text, nullable=True)
    project_id = db.Column(db.Integer, nullable=True)
    contribution_id = db.Column(db.Integer, nullable=True)
    
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    
    __table_args__ = (
        Index('idx_analytics_event_type_created', 'event_type', 'created_at'),
        Index('idx_analytics_user_created', 'user_id', 'created_at'),
        Index('idx_analytics_project_events', 'project_id', 'event_type'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'event_type': self.event_type,
            'user_id': self.user_id,
            'page_url': self.page_url,
            'event_data': self.event_data,
            'project_id': self.project_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }