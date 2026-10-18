"""
Initialisation du package models
Exporte tous les modèles pour un import facile
"""

from app.models.user import User
from app.models.project import Project
from app.models.contribution import Contribution
from app.models.group_contribution import GroupContribution, GroupContributionInvite
from app.models.collection_point import CollectionPoint, ProjectCollectionPoint
from app.models.diaspora_campaign import DiasporaCampaign
from app.models.fund_transfer import FundTransfer, InternationalTransferPartner
from app.models.harvest_update import HarvestUpdate
from app.models.training import Training, TrainingProgress
from app.models.weather import WeatherAlert, WeatherSubscription
from app.models.payment_gateway import PaymentGatewayConfig
from app.models.notification import Notification
from app.models.platform_commission import (
    PlatformCommissionConfig, 
    PlatformEarning, 
    CEOPayout,
    CommissionAuditLog
)
from app.models.analytics import AnalyticsEvent
from app.models.audit import AuditLog
from app.models.enums import (
    UserRole,
    ProjectStatus,
    ContributionStatus,
    PaymentGateway,
    TransferMethod,
    TrainingType,
    CommissionType,
    AlertSeverity,
    AlertType
)

__all__ = [
    'User',
    'Project',
    'Contribution',
    'GroupContribution',
    'GroupContributionInvite',
    'CollectionPoint',
    'ProjectCollectionPoint',
    'DiasporaCampaign',
    'FundTransfer',
    'InternationalTransferPartner',
    'HarvestUpdate',
    'Training',
    'TrainingProgress',
    'WeatherAlert',
    'WeatherSubscription',
    'PaymentGatewayConfig',
    'PlatformCommissionConfig',
    'PlatformEarning',
    'CEOPayout',
    'CommissionAuditLog',
    'AnalyticsEvent',
    'AuditLog',
    'Notification',
    # Enums
    'UserRole',
    'ProjectStatus',
    'ContributionStatus',
    'PaymentGateway',
    'TransferMethod',
    'TrainingType',
    'CommissionType',
    'AlertSeverity',
    'AlertType'
]