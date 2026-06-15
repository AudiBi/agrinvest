# app/utils/analytics.py
"""
Analytique et suivi pour AgriInvest Haïti
"""

from flask import request, session, current_app
from app.extensions import db
from app.models import AnalyticsEvent
from datetime import datetime, timedelta
import json


def track_user_action(user_id, action, resource_type=None, resource_id=None, data=None):
    """
    Enregistre une action utilisateur
    
    Args:
        user_id: ID de l'utilisateur
        action: Action effectuée
        resource_type: Type de ressource
        resource_id: ID de la ressource
        data: Données supplémentaires
    """
    event = AnalyticsEvent(
        user_id=user_id,
        event_type=action,
        page_url=request.url,
        referrer=request.referrer,
        user_agent=request.user_agent.string if request.user_agent else None,
        ip_address=request.remote_addr,
        event_data=json.dumps(data) if data else None,
        project_id=resource_id if resource_type == 'project' else None,
        contribution_id=resource_id if resource_type == 'contribution' else None
    )
    db.session.add(event)
    db.session.commit()


def track_page_view(user_id, page_url, project_id=None):
    """
    Enregistre une vue de page
    """
    track_user_action(user_id, 'page_view', 'project' if project_id else None, project_id, {'url': page_url})


def generate_investment_report(project_id=None, start_date=None, end_date=None):
    """
    Génère un rapport d'investissement
    
    Args:
        project_id: ID du projet (optionnel)
        start_date: Date de début
        end_date: Date de fin
    
    Returns:
        Dict avec les données du rapport
    """
    from app.models import Contribution, Project
    from app.models.enums import ContributionStatus
    
    if not start_date:
        start_date = datetime.now() - timedelta(days=30)
    if not end_date:
        end_date = datetime.now()
    
    query = Contribution.query.filter(
        Contribution.created_at.between(start_date, end_date),
        Contribution.status == ContributionStatus.COMPLETED
    )
    
    if project_id:
        query = query.filter_by(project_id=project_id)
        project = Project.query.get(project_id)
        project_name = project.title if project else None
    else:
        project_name = "Tous les projets"
    
    contributions = query.all()
    
    total_amount = sum(c.amount_htg for c in contributions)
    total_count = len(contributions)
    average_amount = total_amount / total_count if total_count > 0 else 0
    
    # Par jour
    daily = {}
    for c in contributions:
        day = c.created_at.strftime('%Y-%m-%d')
        daily[day] = daily.get(day, 0) + float(c.amount_htg)
    
    return {
        'project_id': project_id,
        'project_name': project_name,
        'period': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat()
        },
        'total_amount': float(total_amount),
        'total_contributions': total_count,
        'average_amount': float(average_amount),
        'daily_breakdown': [{'date': d, 'amount': a} for d, a in sorted(daily.items())]
    }


def generate_user_activity_report(user_id, days=30):
    """
    Génère un rapport d'activité utilisateur
    
    Args:
        user_id: ID de l'utilisateur
        days: Nombre de jours
    
    Returns:
        Dict avec les données d'activité
    """
    from app.models import AnalyticsEvent
    
    start_date = datetime.now() - timedelta(days=days)
    
    events = AnalyticsEvent.query.filter(
        AnalyticsEvent.user_id == user_id,
        AnalyticsEvent.created_at >= start_date
    ).all()
    
    # Compter par type
    by_type = {}
    for event in events:
        by_type[event.event_type] = by_type.get(event.event_type, 0) + 1
    
    # Par jour
    by_day = {}
    for event in events:
        day = event.created_at.strftime('%Y-%m-%d')
        by_day[day] = by_day.get(day, 0) + 1
    
    return {
        'user_id': user_id,
        'period_days': days,
        'total_actions': len(events),
        'by_type': by_type,
        'by_day': [{'date': d, 'count': c} for d, c in sorted(by_day.items())]
    }