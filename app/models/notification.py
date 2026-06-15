# app/models/notification.py
"""
Modèle Notification pour AgriInvest Haïti
"""

from datetime import datetime, timezone
from app.extensions import db
from app.models.enums import NotificationType


def utc_now():
    return datetime.now(timezone.utc)


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    
    # Relations
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), 
                        nullable=False, index=True)
    
    # Contenu
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(20), default='info')  # info, success, warning, danger
    
    # Liens
    link = db.Column(db.String(500), nullable=True)
    
    # Métadonnées
    is_read = db.Column(db.Boolean, default=False, index=True)
    read_at = db.Column(db.DateTime, nullable=True)
    
    # Données supplémentaires (JSON)
    data = db.Column(db.Text, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relations
    user = db.relationship('User', backref=db.backref('notifications', lazy='dynamic'))
    
    __table_args__ = (
        db.Index('idx_notifications_user_read', 'user_id', 'is_read'),
        db.Index('idx_notifications_created', 'created_at'),
    )
    
    def mark_as_read(self):
        """Marque la notification comme lue"""
        if not self.is_read:
            self.is_read = True
            self.read_at = utc_now()
            db.session.commit()
    
    def mark_as_unread(self):
        """Marque la notification comme non lue"""
        if self.is_read:
            self.is_read = False
            self.read_at = None
            db.session.commit()
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'type': self.notification_type,
            'link': self.link,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'read_at': self.read_at.isoformat() if self.read_at else None
        }
    
    def __repr__(self):
        return f'<Notification {self.title}>'