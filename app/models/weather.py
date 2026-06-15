"""
Modèles pour les alertes météo et abonnements
"""

from datetime import datetime, timezone
from sqlalchemy import Index, UniqueConstraint
from app.extensions import db
from app.models.enums import AlertSeverity, AlertType


def utc_now():
    return datetime.now(timezone.utc)


class WeatherAlert(db.Model):
    __tablename__ = 'weather_alerts'

    id = db.Column(db.Integer, primary_key=True)
    
    zone = db.Column(db.String(50), nullable=False, index=True)
    department = db.Column(db.String(50), nullable=True, index=True)
    
    alert_type = db.Column(db.String(30), nullable=False)
    severity = db.Column(db.String(20), nullable=False)
    
    message_ht = db.Column(db.Text, nullable=False)
    message_fr = db.Column(db.Text, nullable=True)
    message_en = db.Column(db.Text, nullable=True)
    
    agricultural_advice_ht = db.Column(db.Text, nullable=True)
    agricultural_advice_fr = db.Column(db.Text, nullable=True)
    
    starts_at = db.Column(db.DateTime, nullable=False)
    ends_at = db.Column(db.DateTime, nullable=False)
    
    source = db.Column(db.String(50), nullable=True)
    external_id = db.Column(db.String(100), nullable=True)
    
    sent_via_sms = db.Column(db.Boolean, default=False)
    sent_via_whatsapp = db.Column(db.Boolean, default=False)
    sent_at = db.Column(db.DateTime, nullable=True)
    
    is_active = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    __table_args__ = (
        Index('idx_weather_alerts_zone_active', 'zone', 'is_active'),
        Index('idx_weather_alerts_severity', 'severity', 'starts_at'),
        Index('idx_weather_alerts_dates', 'starts_at', 'ends_at'),
    )
    
    def to_dict(self, language='ht'):
        message_field = f'message_{language}' if language in ['ht', 'fr', 'en'] else 'message_ht'
        advice_field = f'agricultural_advice_{language}' if language in ['ht', 'fr', 'en'] else 'agricultural_advice_ht'
        
        return {
            'id': self.id,
            'zone': self.zone,
            'department': self.department,
            'alert_type': self.alert_type,
            'severity': self.severity,
            'message': getattr(self, message_field, self.message_ht),
            'agricultural_advice': getattr(self, advice_field, None),
            'starts_at': self.starts_at.isoformat() if self.starts_at else None,
            'ends_at': self.ends_at.isoformat() if self.ends_at else None,
        }


class WeatherSubscription(db.Model):
    __tablename__ = 'weather_subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    
    farmer_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'),
                          nullable=False, index=True)
    
    zone = db.Column(db.String(50), nullable=False, index=True)
    
    receive_sms = db.Column(db.Boolean, default=True)
    receive_whatsapp = db.Column(db.Boolean, default=False)
    
    min_severity = db.Column(db.String(20), default='warning')
    
    language = db.Column(db.String(10), default='ht')
    
    is_active = db.Column(db.Boolean, default=True)
    phone_number = db.Column(db.String(20), nullable=True)
    
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    last_notified_at = db.Column(db.DateTime, nullable=True)
    
    __table_args__ = (
        UniqueConstraint('farmer_id', 'zone', name='uq_farmer_weather_zone'),
        Index('idx_weather_subscriptions_active', 'is_active', 'zone'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'farmer_id': self.farmer_id,
            'zone': self.zone,
            'receive_sms': self.receive_sms,
            'receive_whatsapp': self.receive_whatsapp,
            'min_severity': self.min_severity,
            'language': self.language,
            'is_active': self.is_active,
            'phone_number': self.phone_number,
        }