"""
Modèle pour les campagnes ciblant la diaspora haïtienne
"""

from datetime import datetime, timezone
from decimal import Decimal
from app.extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class DiasporaCampaign(db.Model):
    __tablename__ = 'diaspora_campaigns'

    id = db.Column(db.Integer, primary_key=True)
    
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    ambassador_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'),
                              nullable=True, index=True)
    
    target_countries = db.Column(db.Text, nullable=False)
    
    matching_fund_percentage = db.Column(db.Numeric(5, 2), default=0)
    matching_fund_cap = db.Column(db.Numeric(12, 2), nullable=True)
    
    diaspora_specific_message = db.Column(db.Text, nullable=True)
    diaspora_specific_message_ht = db.Column(db.Text, nullable=True)
    ambassador_video_url = db.Column(db.String(500), nullable=True)
    
    ambassador_commission = db.Column(db.Numeric(5, 2), default=0)
    
    virtual_townhall_link = db.Column(db.String(500), nullable=True)
    virtual_townhall_date = db.Column(db.DateTime, nullable=True)
    fundraising_events = db.Column(db.Text, nullable=True)
    
    whatsapp_group_link = db.Column(db.String(200), nullable=True)
    facebook_event_link = db.Column(db.String(200), nullable=True)
    
    contributions_count = db.Column(db.Integer, default=0)
    total_amount_raised = db.Column(db.Numeric(12, 2), default=0)
    email_campaign_sent = db.Column(db.Boolean, default=False)
    
    status = db.Column(db.String(20), default='active')
    
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    completed_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'project_title': self.project.title if self.project else None,
            'ambassador_name': self.ambassador.name if self.ambassador else None,
            'target_countries': self.target_countries,
            'matching_fund_percentage': float(self.matching_fund_percentage) if self.matching_fund_percentage else 0,
            'total_amount_raised': float(self.total_amount_raised),
            'virtual_townhall_link': self.virtual_townhall_link,
            'virtual_townhall_date': self.virtual_townhall_date.isoformat() if self.virtual_townhall_date else None,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }