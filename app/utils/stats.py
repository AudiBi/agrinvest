# app/utils/stats.py
"""
Fonctions statistiques pour la plateforme AgriInvest Haïti
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from app.models.platform_commission import CEOPayout
from sqlalchemy import func, and_, or_
from app.extensions import db
from app.models import (
    User, Project, Contribution, PlatformEarning, 
    WeatherAlert, Training, TrainingProgress, GroupContribution,
    DiasporaCampaign, FundTransfer, WeatherSubscription
)
from app.models.enums import ContributionStatus, ProjectStatus, UserRole


def utc_now():
    """Retourne la date UTC actuelle"""
    return datetime.now(timezone.utc)


def get_platform_stats():
    """
    Statistiques globales de la plateforme
    Utilisé par le dashboard admin
    """
    
    # =========================================================================
    # STATISTIQUES UTILISATEURS
    # =========================================================================
    total_users = User.query.count()
    total_farmers = User.query.filter_by(role=UserRole.FARMER).count()
    total_investors = User.query.filter_by(role=UserRole.INVESTOR).count()
    total_ambassadors = User.query.filter_by(role=UserRole.AMBASSADOR).count()
    total_agents = User.query.filter_by(role=UserRole.AGENT).count()
    
    # Utilisateurs par pays
    users_by_country = db.session.query(
        User.country, func.count(User.id)
    ).filter(User.country.isnot(None)).group_by(User.country).all()
    
    # Diaspora vs local
    diaspora_count = User.query.filter(User.country != 'HT', User.country.isnot(None)).count()
    local_count = User.query.filter_by(country='HT').count()
    
    # Nouveaux utilisateurs (30 jours)
    thirty_days_ago = utc_now() - timedelta(days=30)
    new_users_last_30d = User.query.filter(User.created_at >= thirty_days_ago).count()
    
    # Utilisateurs vérifiés
    verified_users = User.query.filter_by(is_verified=True).count()
    
    # =========================================================================
    # STATISTIQUES PROJETS
    # =========================================================================
    total_projects = Project.query.count()
    published_projects = Project.query.filter_by(is_published=True).count()
    funded_projects = Project.query.filter_by(status=ProjectStatus.FUNDED).count()
    draft_projects = Project.query.filter_by(status=ProjectStatus.DRAFT).count()
    expired_projects = Project.query.filter_by(status=ProjectStatus.EXPIRED).count()
    pending_projects = Project.query.filter_by(status=ProjectStatus.PENDING).count()
    
    # Projets par catégorie
    projects_by_category = db.session.query(
        Project.category, func.count(Project.id)
    ).filter(Project.category.isnot(None)).group_by(Project.category).all()
    
    # Projets par département
    projects_by_department = db.session.query(
        Project.department, func.count(Project.id)
    ).filter(Project.department.isnot(None)).group_by(Project.department).all()
    
    # Projets à la une
    featured_projects = Project.query.filter_by(is_featured=True, is_published=True).count()
    
    # Taux de succès des projets
    if published_projects > 0:
        success_rate = (funded_projects / published_projects) * 100
    else:
        success_rate = 0
    
    # Montant total recherché
    total_amount_needed = db.session.query(func.sum(Project.amount_needed)).filter_by(
        is_published=True
    ).scalar() or 0
    
    # =========================================================================
    # STATISTIQUES CONTRIBUTIONS
    # =========================================================================
    total_contributions = Contribution.query.filter_by(
        status=ContributionStatus.COMPLETED
    ).count()
    
    total_raised_htg = db.session.query(
        func.sum(Contribution.amount_htg)
    ).filter_by(status=ContributionStatus.COMPLETED).scalar() or 0
    
    total_raised_usd = db.session.query(
        func.sum(Contribution.amount)
    ).filter_by(
        status=ContributionStatus.COMPLETED,
        currency='USD'
    ).scalar() or 0
    
    total_raised_eur = db.session.query(
        func.sum(Contribution.amount)
    ).filter_by(
        status=ContributionStatus.COMPLETED,
        currency='EUR'
    ).scalar() or 0
    
    total_raised_cad = db.session.query(
        func.sum(Contribution.amount)
    ).filter_by(
        status=ContributionStatus.COMPLETED,
        currency='CAD'
    ).scalar() or 0
    
    # Contribution moyenne
    if total_contributions > 0:
        average_contribution = total_raised_htg / total_contributions
    else:
        average_contribution = 0
    
    # Contributions par pays
    contributions_by_country = db.session.query(
        Contribution.investor_country, 
        func.count(Contribution.id),
        func.sum(Contribution.amount_htg)
    ).filter_by(status=ContributionStatus.COMPLETED).group_by(
        Contribution.investor_country
    ).all()
    
    # Contributions de la diaspora
    diaspora_contributions = Contribution.query.filter(
        Contribution.status == ContributionStatus.COMPLETED,
        Contribution.investor_country != 'HT',
        Contribution.investor_country.isnot(None)
    ).count()
    
    diaspora_amount = db.session.query(
        func.sum(Contribution.amount_htg)
    ).filter(
        Contribution.status == ContributionStatus.COMPLETED,
        Contribution.investor_country != 'HT',
        Contribution.investor_country.isnot(None)
    ).scalar() or 0
    
    # Contributions locales
    local_contributions = total_contributions - diaspora_contributions
    local_amount = total_raised_htg - diaspora_amount
    
    # Pourcentage diaspora
    if total_raised_htg > 0:
        diaspora_percentage = (diaspora_amount / total_raised_htg) * 100
    else:
        diaspora_percentage = 0
    
    # Contributions par méthode de paiement
    contributions_by_payment = db.session.query(
        Contribution.payment_method, 
        func.count(Contribution.id),
        func.sum(Contribution.amount_htg)
    ).filter_by(status=ContributionStatus.COMPLETED).group_by(
        Contribution.payment_method
    ).all()
    
    # =========================================================================
    # STATISTIQUES FINANCIÈRES PLATEFORME
    # =========================================================================
    total_platform_earnings = db.session.query(
        func.sum(PlatformEarning.commission_amount_htg)
    ).filter(PlatformEarning.status == 'paid').scalar() or 0
    
    pending_earnings = db.session.query(
        func.sum(PlatformEarning.commission_amount_htg)
    ).filter(PlatformEarning.status == 'pending').scalar() or 0
    
    total_paid_to_ceo = db.session.query(
        func.sum(CEOPayout.payout_amount)
    ).filter(CEOPayout.status == 'completed').scalar() or 0
    
    # Commissions par type
    earnings_by_type = db.session.query(
        PlatformEarning.earning_type,
        func.sum(PlatformEarning.commission_amount_htg)
    ).group_by(PlatformEarning.earning_type).all()
    
    # =========================================================================
    # STATISTIQUES TRANSFERTS
    # =========================================================================
    total_transferred = db.session.query(
        func.sum(FundTransfer.amount_htg)
    ).filter(FundTransfer.status == 'completed').scalar() or 0
    
    pending_transfers = db.session.query(
        func.sum(FundTransfer.amount_htg)
    ).filter(FundTransfer.status == 'pending').scalar() or 0
    
    transfers_count = FundTransfer.query.count()
    completed_transfers = FundTransfer.query.filter_by(status='completed').count()
    
    # =========================================================================
    # STATISTIQUES FORMATIONS
    # =========================================================================
    total_trainings = Training.query.filter_by(is_published=True).count()
    trainings_by_category = db.session.query(
        Training.category, func.count(Training.id)
    ).filter_by(is_published=True).group_by(Training.category).all()
    
    # Progression des formations
    total_farmers_training = TrainingProgress.query.distinct('farmer_id').count()
    completed_trainings = TrainingProgress.query.filter_by(status='completed').count()
    certificates_issued = TrainingProgress.query.filter_by(certificate_generated=True).count()
    
    # =========================================================================
    # STATISTIQUES MÉTÉO
    # =========================================================================
    active_alerts = WeatherAlert.query.filter(
        WeatherAlert.is_active == True,
        WeatherAlert.ends_at >= utc_now()
    ).count()
    
    critical_alerts = WeatherAlert.query.filter_by(
        severity='critical',
        is_active=True
    ).count()
    
    weather_subscribers = WeatherSubscription.query.filter_by(is_active=True).count()
    
    # =========================================================================
    # STATISTIQUES GROUPES ET DIASPORA
    # =========================================================================
    total_groups = GroupContribution.query.count()
    active_groups = GroupContribution.query.filter_by(status='active').count()
    groups_amount_raised = db.session.query(
        func.sum(GroupContribution.current_amount)
    ).scalar() or 0
    
    diaspora_campaigns = DiasporaCampaign.query.filter_by(status='active').count()
    total_campaign_raised = db.session.query(
        func.sum(DiasporaCampaign.total_amount_raised)
    ).scalar() or 0
    
    # =========================================================================
    # ÉVOLUTIONS TEMPORELLES (30 derniers jours)
    # =========================================================================
    daily_stats = []
    for i in range(30):
        day = utc_now() - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        day_users = User.query.filter(
            User.created_at.between(day_start, day_end)
        ).count()
        
        day_projects = Project.query.filter(
            Project.created_at.between(day_start, day_end)
        ).count()
        
        day_contributions = Contribution.query.filter(
            Contribution.created_at.between(day_start, day_end),
            Contribution.status == ContributionStatus.COMPLETED
        ).count()
        
        day_amount = db.session.query(
            func.sum(Contribution.amount_htg)
        ).filter(
            Contribution.created_at.between(day_start, day_end),
            Contribution.status == ContributionStatus.COMPLETED
        ).scalar() or 0
        
        daily_stats.append({
            'date': day.strftime('%Y-%m-%d'),
            'new_users': day_users,
            'new_projects': day_projects,
            'contributions': day_contributions,
            'amount_raised': float(day_amount)
        })
    
    # =========================================================================
    # CONSTRUCTION DU RÉSULTAT FINAL
    # =========================================================================
    
    return {
        # Utilisateurs
        'users': {
            'total': total_users,
            'farmers': total_farmers,
            'investors': total_investors,
            'ambassadors': total_ambassadors,
            'agents': total_agents,
            'diaspora': diaspora_count,
            'local': local_count,
            'verified': verified_users,
            'new_last_30d': new_users_last_30d,
            'by_country': [
                {'country': c[0], 'count': c[1]} 
                for c in users_by_country
            ]
        },
        
        # Projets
        'projects': {
            'total': total_projects,
            'published': published_projects,
            'funded': funded_projects,
            'draft': draft_projects,
            'expired': expired_projects,
            'pending': pending_projects,
            'featured': featured_projects,
            'success_rate': round(success_rate, 2),
            'total_amount_needed': float(total_amount_needed),
            'by_category': [
                {'category': c[0], 'count': c[1]} 
                for c in projects_by_category
            ],
            'by_department': [
                {'department': d[0], 'count': d[1]} 
                for d in projects_by_department
            ]
        },
        
        # Contributions
        'contributions': {
            'total': total_contributions,
            'total_raised_htg': float(total_raised_htg),
            'total_raised_usd': float(total_raised_usd),
            'total_raised_eur': float(total_raised_eur),
            'total_raised_cad': float(total_raised_cad),
            'average_contribution_htg': float(average_contribution),
            'diaspora': {
                'count': diaspora_contributions,
                'amount_htg': float(diaspora_amount),
                'percentage': round(diaspora_percentage, 2)
            },
            'local': {
                'count': local_contributions,
                'amount_htg': float(local_amount)
            },
            'by_country': [
                {
                    'country': c[0],
                    'count': c[1],
                    'amount_htg': float(c[2])
                } for c in contributions_by_country
            ],
            'by_payment_method': [
                {
                    'method': p[0],
                    'count': p[1],
                    'amount_htg': float(p[2])
                } for p in contributions_by_payment
            ]
        },
        
        # Finances plateforme
        'platform_finances': {
            'total_earnings_htg': float(total_platform_earnings),
            'pending_earnings_htg': float(pending_earnings),
            'paid_to_ceo_htg': float(total_paid_to_ceo),
            'by_type': [
                {'type': t[0], 'amount_htg': float(t[1])} 
                for t in earnings_by_type
            ]
        },
        
        # Transferts
        'transfers': {
            'total_transferred_htg': float(total_transferred),
            'pending_transfers_htg': float(pending_transfers),
            'total_batches': transfers_count,
            'completed_batches': completed_transfers
        },
        
        # Formations
        'trainings': {
            'total': total_trainings,
            'by_category': [
                {'category': c[0], 'count': c[1]} 
                for c in trainings_by_category
            ],
            'farmers_trained': total_farmers_training,
            'completed_trainings': completed_trainings,
            'certificates_issued': certificates_issued
        },
        
        # Météo
        'weather': {
            'active_alerts': active_alerts,
            'critical_alerts': critical_alerts,
            'subscribers': weather_subscribers
        },
        
        # Groupes et diaspora
        'groups_campaigns': {
            'total_groups': total_groups,
            'active_groups': active_groups,
            'groups_amount_raised': float(groups_amount_raised),
            'active_campaigns': diaspora_campaigns,
            'campaigns_amount_raised': float(total_campaign_raised)
        },
        
        # Évolution temporelle
        'daily_stats': daily_stats,
        
        # Métadonnées
        'generated_at': utc_now().isoformat()
    }


def get_project_stats(project_id):
    """
    Statistiques détaillées pour un projet spécifique
    """
    project = Project.query.get_or_404(project_id)
    
    # Contributions
    contributions = Contribution.query.filter_by(
        project_id=project_id,
        status=ContributionStatus.COMPLETED
    )
    
    total_contributors = contributions.distinct('investor_id').count()
    total_contributions = contributions.count()
    total_amount = contributions.with_entities(
        func.sum(Contribution.amount_htg)
    ).scalar() or 0
    
    # Contributions par jour
    daily_contributions = []
    for i in range(30):
        day = utc_now() - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        day_count = contributions.filter(
            Contribution.created_at.between(day_start, day_end)
        ).count()
        
        day_amount = contributions.filter(
            Contribution.created_at.between(day_start, day_end)
        ).with_entities(func.sum(Contribution.amount_htg)).scalar() or 0
        
        daily_contributions.append({
            'date': day.strftime('%Y-%m-%d'),
            'count': day_count,
            'amount': float(day_amount)
        })
    
    # Top contributeurs
    top_contributors = db.session.query(
        User.name, User.id,
        func.sum(Contribution.amount_htg).label('total')
    ).join(
        Contribution, Contribution.investor_id == User.id
    ).filter(
        Contribution.project_id == project_id,
        Contribution.status == ContributionStatus.COMPLETED
    ).group_by(
        User.id
    ).order_by(
        func.sum(Contribution.amount_htg).desc()
    ).limit(10).all()
    
    # Contributions par pays
    by_country = db.session.query(
        Contribution.investor_country,
        func.count(Contribution.id),
        func.sum(Contribution.amount_htg)
    ).filter(
        Contribution.project_id == project_id,
        Contribution.status == ContributionStatus.COMPLETED
    ).group_by(Contribution.investor_country).all()
    
    # Vues du projet
    from app.models import AnalyticsEvent
    views = AnalyticsEvent.query.filter_by(
        project_id=project_id,
        event_type='project_view'
    ).count()
    
    # Taux de conversion
    conversion_rate = (total_contributions / views * 100) if views > 0 else 0
    
    return {
        'project_id': project_id,
        'project_title': project.title,
        'status': project.status,
        'progress': project.progress_percentage,
        'statistics': {
            'total_raised': float(total_amount),
            'total_contributors': total_contributors,
            'total_contributions': total_contributions,
            'average_contribution': float(total_amount / total_contributions) if total_contributions > 0 else 0,
            'views': views,
            'conversion_rate': round(conversion_rate, 2)
        },
        'daily_breakdown': daily_contributions,
        'top_contributors': [
            {'name': c[0], 'id': c[1], 'total': float(c[2])} 
            for c in top_contributors
        ],
        'by_country': [
            {'country': c[0] or 'unknown', 'count': c[1], 'amount': float(c[2])}
            for c in by_country
        ]
    }


def get_user_stats(user_id):
    """
    Statistiques détaillées pour un utilisateur spécifique
    """
    user = User.query.get_or_404(user_id)
    
    stats = {
        'user_id': user.id,
        'name': user.name,
        'role': user.role,
        'member_since': user.created_at.isoformat(),
        'is_verified': user.is_verified,
        'is_diaspora': user.is_diaspora,
        'country': user.country
    }
    
    if user.is_investor or user.is_admin:
        # Contributions de l'investisseur
        contributions = Contribution.query.filter_by(
            investor_id=user_id,
            status=ContributionStatus.COMPLETED
        )
        
        total_invested = contributions.with_entities(
            func.sum(Contribution.amount_htg)
        ).scalar() or 0
        
        projects_supported = contributions.distinct('project_id').count()
        total_contributions = contributions.count()
        
        # Par projet
        by_project = db.session.query(
            Project.title, Project.id,
            func.sum(Contribution.amount_htg).label('total')
        ).join(
            Contribution, Contribution.project_id == Project.id
        ).filter(
            Contribution.investor_id == user_id,
            Contribution.status == ContributionStatus.COMPLETED
        ).group_by(Project.id).order_by(
            func.sum(Contribution.amount_htg).desc()
        ).all()
        
        stats['investor'] = {
            'total_invested_htg': float(total_invested),
            'projects_supported': projects_supported,
            'total_contributions': total_contributions,
            'average_investment': float(total_invested / total_contributions) if total_contributions > 0 else 0,
            'by_project': [
                {'project_id': p[1], 'title': p[0], 'amount': float(p[2])}
                for p in by_project
            ]
        }
    
    if user.is_farmer or user.is_admin:
        # Projets de l'agriculteur
        projects = Project.query.filter_by(farmer_id=user_id)
        
        total_projects = projects.count()
        published_projects = projects.filter_by(is_published=True).count()
        funded_projects = projects.filter_by(status=ProjectStatus.FUNDED).count()
        total_raised = projects.with_entities(
            func.sum(Project.amount_raised)
        ).scalar() or 0
        
        # Contributions reçues
        contributions_received = Contribution.query.join(
            Project
        ).filter(
            Project.farmer_id == user_id,
            Contribution.status == ContributionStatus.COMPLETED
        )
        
        total_contributions = contributions_received.count()
        total_contributors = contributions_received.distinct('investor_id').count()
        
        stats['farmer'] = {
            'total_projects': total_projects,
            'published_projects': published_projects,
            'funded_projects': funded_projects,
            'total_raised_htg': float(total_raised),
            'total_contributors': total_contributors,
            'total_contributions': total_contributions
        }
    
    if user.is_ambassador:
        # Campagnes de l'ambassadeur
        campaigns = DiasporaCampaign.query.filter_by(ambassador_id=user_id)
        
        total_campaigns = campaigns.count()
        active_campaigns = campaigns.filter_by(status='active').count()
        total_raised = campaigns.with_entities(
            func.sum(DiasporaCampaign.total_amount_raised)
        ).scalar() or 0
        
        stats['ambassador'] = {
            'total_campaigns': total_campaigns,
            'active_campaigns': active_campaigns,
            'total_raised': float(total_raised)
        }
    
    return stats


def get_diaspora_stats():
    """
    Statistiques spécifiques à la diaspora
    """
    # Diaspora par pays
    diaspora_by_country = db.session.query(
        User.country,
        func.count(User.id),
        func.sum(Contribution.amount_htg).label('total_invested')
    ).join(
        Contribution, Contribution.investor_id == User.id, isouter=True
    ).filter(
        User.country != 'HT',
        User.country.isnot(None),
        Contribution.status == ContributionStatus.COMPLETED
    ).group_by(User.country).all()
    
    # Top pays donateurs
    top_countries = sorted(diaspora_by_country, key=lambda x: x[2] or 0, reverse=True)[:10]
    
    # Évolution des dons diaspora
    monthly_diaspora = []
    for i in range(12):
        month_start = utc_now().replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30*i)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(microseconds=1)
        
        amount = db.session.query(
            func.sum(Contribution.amount_htg)
        ).filter(
            Contribution.investor_country != 'HT',
            Contribution.investor_country.isnot(None),
            Contribution.status == ContributionStatus.COMPLETED,
            Contribution.created_at.between(month_start, month_end)
        ).scalar() or 0
        
        monthly_diaspora.append({
            'month': month_start.strftime('%Y-%m'),
            'amount_htg': float(amount)
        })
    
    # Campagnes diaspora
    campaigns = DiasporaCampaign.query.all()
    
    total_campaigns = len(campaigns)
    active_campaigns = sum(1 for c in campaigns if c.status == 'active')
    total_raised = sum(c.total_amount_raised for c in campaigns)
    
    return {
        'diaspora_stats': {
            'countries_represented': len(diaspora_by_country),
            'total_diaspora_members': sum(c[1] for c in diaspora_by_country),
            'total_invested_by_diaspora': float(sum(c[2] or 0 for c in diaspora_by_country)),
            'top_countries': [
                {
                    'country': c[0],
                    'members': c[1],
                    'invested': float(c[2] or 0)
                } for c in top_countries
            ],
            'monthly_trend': monthly_diaspora
        },
        'campaigns': {
            'total': total_campaigns,
            'active': active_campaigns,
            'total_raised': float(total_raised),
            'matching_funds_available': float(sum(c.matching_fund_cap or 0 for c in campaigns))
        }
    }


def get_growth_stats(period='month'):
    """
    Statistiques de croissance
    period: 'week', 'month', 'year'
    """
    if period == 'week':
        days = 7
    elif period == 'month':
        days = 30
    else:
        days = 365
    
    start_date = utc_now() - timedelta(days=days)
    
    # Nouveaux utilisateurs
    new_users = User.query.filter(User.created_at >= start_date).count()
    previous_users = User.query.filter(
        User.created_at < start_date,
        User.created_at >= start_date - timedelta(days=days)
    ).count()
    
    user_growth = ((new_users - previous_users) / previous_users * 100) if previous_users > 0 else 0
    
    # Nouveaux projets
    new_projects = Project.query.filter(Project.created_at >= start_date).count()
    previous_projects = Project.query.filter(
        Project.created_at < start_date,
        Project.created_at >= start_date - timedelta(days=days)
    ).count()
    
    project_growth = ((new_projects - previous_projects) / previous_projects * 100) if previous_projects > 0 else 0
    
    # Nouvelles contributions
    new_contributions = Contribution.query.filter(
        Contribution.created_at >= start_date,
        Contribution.status == ContributionStatus.COMPLETED
    ).count()
    
    new_amount = db.session.query(
        func.sum(Contribution.amount_htg)
    ).filter(
        Contribution.created_at >= start_date,
        Contribution.status == ContributionStatus.COMPLETED
    ).scalar() or 0
    
    previous_contributions = Contribution.query.filter(
        Contribution.created_at < start_date,
        Contribution.created_at >= start_date - timedelta(days=days),
        Contribution.status == ContributionStatus.COMPLETED
    ).count()
    
    contribution_growth = ((new_contributions - previous_contributions) / previous_contributions * 100) if previous_contributions > 0 else 0
    
    return {
        'period': period,
        'days': days,
        'start_date': start_date.isoformat(),
        'users': {
            'new': new_users,
            'previous': previous_users,
            'growth_percentage': round(user_growth, 2)
        },
        'projects': {
            'new': new_projects,
            'previous': previous_projects,
            'growth_percentage': round(project_growth, 2)
        },
        'contributions': {
            'new_count': new_contributions,
            'new_amount_htg': float(new_amount),
            'previous_count': previous_contributions,
            'growth_percentage': round(contribution_growth, 2)
        }
    }


def get_financial_summary():
    """
    Résumé financier de la plateforme
    """
    # Total collecté
    total_collected = db.session.query(
        func.sum(Contribution.amount_htg)
    ).filter_by(status=ContributionStatus.COMPLETED).scalar() or 0
    
    # Total transféré aux agriculteurs
    total_transferred_to_farmers = db.session.query(
        func.sum(PlatformEarning.net_to_project)
    ).filter(PlatformEarning.status == 'paid').scalar() or 0
    
    # Commissions plateforme
    total_commission = db.session.query(
        func.sum(PlatformEarning.commission_amount_htg)
    ).filter(PlatformEarning.status == 'paid').scalar() or 0
    
    # Frais de paiement
    total_gateway_fees = db.session.query(
        func.sum(Contribution.gateway_fee)
    ).filter_by(status=ContributionStatus.COMPLETED).scalar() or 0
    
    # Frais de change
    total_conversion_fees = db.session.query(
        func.sum(Contribution.conversion_fee)
    ).filter_by(status=ContributionStatus.COMPLETED).scalar() or 0
    
    # En attente de transfert
    pending_transfer = db.session.query(
        func.sum(Contribution.amount_htg)
    ).filter_by(
        status=ContributionStatus.COMPLETED,
        transfer_batch_id=None
    ).scalar() or 0
    
    return {
        'total_collected_htg': float(total_collected),
        'transferred_to_farmers_htg': float(total_transferred_to_farmers),
        'platform_commission_htg': float(total_commission),
        'gateway_fees_htg': float(total_gateway_fees),
        'conversion_fees_htg': float(total_conversion_fees),
        'pending_transfer_htg': float(pending_transfer),
        'platform_net_income_htg': float(total_commission - total_gateway_fees - total_conversion_fees)
    }


def get_impact_stats():
    """
    Statistiques d'impact social et environnemental
    """
    # Projets financés
    funded_projects = Project.query.filter_by(status=ProjectStatus.FUNDED).all()
    
    total_jobs_created = sum(p.estimated_jobs or 0 for p in funded_projects)
    total_farmers_helped = sum(p.estimated_farmers_helped or 0 for p in funded_projects)
    total_co2_reduction = sum(p.co2_reduction_kg or 0 for p in funded_projects)
    
    # Par département
    impact_by_department = db.session.query(
        Project.department,
        func.sum(Project.estimated_jobs).label('jobs'),
        func.sum(Project.estimated_farmers_helped).label('farmers'),
        func.sum(Project.co2_reduction_kg).label('co2')
    ).filter(
        Project.status == ProjectStatus.FUNDED,
        Project.department.isnot(None)
    ).group_by(Project.department).all()
    
    # Témoignages (à compléter)
    testimonials_count = 0  # À implémenter avec un modèle Testimonial
    
    return {
        'funded_projects_count': len(funded_projects),
        'total_jobs_created': total_jobs_created,
        'total_farmers_helped': total_farmers_helped,
        'total_co2_reduction_kg': float(total_co2_reduction),
        'by_department': [
            {
                'department': d[0],
                'jobs': d[1] or 0,
                'farmers': d[2] or 0,
                'co2_reduction_kg': float(d[3] or 0)
            } for d in impact_by_department
        ],
        'testimonials_count': testimonials_count
    }


def get_export_stats(format='json'):
    """
    Exporte toutes les statistiques pour rapport ou API externe
    """
    stats = {
        'platform': get_platform_stats(),
        'financial': get_financial_summary(),
        'impact': get_impact_stats(),
        'growth': {
            'month': get_growth_stats('month'),
            'year': get_growth_stats('year')
        },
        'diaspora': get_diaspora_stats(),
        'generated_at': utc_now().isoformat(),
        'version': '1.0'
    }
    
    return stats