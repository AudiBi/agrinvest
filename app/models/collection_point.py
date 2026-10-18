"""
Modèles pour les points de collecte physiques (cash en Haïti)
"""

from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Index
from app.extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class CollectionPoint(db.Model):
    __tablename__ = 'collection_points'

    id = db.Column(db.Integer, primary_key=True)
    
    name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(50), nullable=False, index=True)
    commune = db.Column(db.String(50), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    
    manager_name = db.Column(db.String(100))
    manager_phone = db.Column(db.String(20))
    
    opening_hours = db.Column(db.String(200), nullable=True)
    
    is_active = db.Column(db.Boolean, default=True)
    
    fee_percentage = db.Column(db.Numeric(5, 2), default=0)
    
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    contributions = db.relationship('Contribution', backref='collection_point', lazy='dynamic')
    project_links = db.relationship('ProjectCollectionPoint', backref='collection_point', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'department': self.department,
            'commune': self.commune,
            'address': self.address,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'manager_name': self.manager_name,
            'manager_phone': self.manager_phone,
            'opening_hours': self.opening_hours,
            'is_active': self.is_active,
        }


class ProjectCollectionPoint(db.Model):
    __tablename__ = 'project_collection_points'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    collection_point_id = db.Column(db.Integer, db.ForeignKey('collection_points.id', ondelete='CASCADE'),
                                    nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utc_now)

    __table_args__ = (
        Index('idx_project_collection_unique', 'project_id', 'collection_point_id', unique=True),
    )


class CollectionPointAgent(db.Model):
    """Agent autorisé à encaisser des espèces à un point de collecte."""
    __tablename__ = 'collection_point_agents'

    id = db.Column(db.Integer, primary_key=True)
    collection_point_id = db.Column(db.Integer, db.ForeignKey('collection_points.id', ondelete='CASCADE'),
                                    nullable=False, index=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'),
                         nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utc_now)

    point = db.relationship('CollectionPoint', backref=db.backref('agent_links', lazy='dynamic'))
    agent = db.relationship('User')

    __table_args__ = (
        Index('idx_collection_point_agent_unique', 'collection_point_id', 'agent_id', unique=True),
    )
