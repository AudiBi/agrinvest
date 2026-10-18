"""
Routes pour l'analytique
"""

import json
from datetime import datetime, timedelta
from flask import request, jsonify, Blueprint
from flask_login import login_required, current_user
from app.api import api_bp
from app.models import AnalyticsEvent, User, Project, Contribution
from app.extensions import db
from app.utils.decorators import admin_required, rate_limit


analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')


def _parse_day(value):
    """AAAA-MM-JJ -> datetime naïf (minuit UTC), ou None si absent. ValueError si invalide."""
    return datetime.strptime(value, '%Y-%m-%d') if value else None


@analytics_bp.route('/track', methods=['POST'])
@rate_limit(limit=120, per=60)  # endpoint public : on borne l'écriture en base par IP
def track_event():
    """Enregistre un événement analytique"""
    data = request.get_json(silent=True) or {}
    if not isinstance(data.get('event_type'), str) or not data['event_type'] or len(data['event_type']) > 50:
        return jsonify({'error': 'event_type requis (50 caractères max)'}), 400
    for field in ('project_id', 'contribution_id'):
        if data.get(field) is not None and (isinstance(data[field], bool) or not isinstance(data[field], int)):
            return jsonify({'error': f'{field} doit être un entier'}), 400

    # event_data est une colonne texte : un objet JSON est sérialisé, la taille est bornée
    event_data = data.get('event_data')
    if event_data is not None and not isinstance(event_data, str):
        event_data = json.dumps(event_data, ensure_ascii=False)
    if event_data and len(event_data) > 5000:
        return jsonify({'error': 'event_data trop volumineux (5000 caractères max)'}), 400

    def clip(value, limit=500):  # colonnes varchar(500) : on tronque au lieu de provoquer une erreur 500
        return value[:limit] if isinstance(value, str) else None
    
    event = AnalyticsEvent(
        event_type=data['event_type'],
        user_id=current_user.id if current_user.is_authenticated else None,
        page_url=clip(data.get('page_url')),
        referrer=clip(data.get('referrer')),
        user_agent=clip(request.headers.get('User-Agent')),
        ip_address=request.remote_addr,
        event_data=event_data,
        project_id=data.get('project_id'),
        contribution_id=data.get('contribution_id')
    )
    
    db.session.add(event)
    db.session.commit()
    
    return jsonify({'status': 'ok'}), 200


@analytics_bp.route('/stats/conversion', methods=['GET'])
@login_required
@admin_required
def get_conversion_stats():
    """Statistiques de conversion"""
    try:
        start_date = _parse_day(request.args.get('start_date'))
        end_date = _parse_day(request.args.get('end_date'))
    except ValueError:
        return jsonify({'error': 'start_date / end_date : format AAAA-MM-JJ attendu'}), 400

    def count(event_type):
        query = AnalyticsEvent.query.filter_by(event_type=event_type)
        if start_date:
            query = query.filter(AnalyticsEvent.created_at >= start_date)
        if end_date:  # la date de fin est incluse
            query = query.filter(AnalyticsEvent.created_at < end_date + timedelta(days=1))
        return query.count()

    # Compter les événements par type, sur la période demandée
    page_views = count('page_view')
    contribution_starts = count('contribution_start')
    contribution_completes = count('contribution_complete')
    
    conversion_rate = (contribution_completes / contribution_starts * 100) if contribution_starts > 0 else 0
    
    return jsonify({
        'page_views': page_views,
        'contribution_starts': contribution_starts,
        'contribution_completes': contribution_completes,
        'conversion_rate': round(conversion_rate, 2)
    }), 200


@analytics_bp.route('/stats/traffic', methods=['GET'])
@login_required
@admin_required
def get_traffic_stats():
    """Statistiques de trafic par jour"""
    days = max(1, min(request.args.get('days', 30, type=int), 365))
    
    from app.utils.date_utils import get_last_days
    
    result = []
    for day in get_last_days(days):
        count = AnalyticsEvent.query.filter(
            AnalyticsEvent.created_at.between(day['start'], day['end'])
        ).count()
        
        result.append({
            'date': day['date'],
            'count': count
        })
    
    return jsonify(result), 200


@analytics_bp.route('/stats/project/<int:project_id>', methods=['GET'])
@login_required
def get_project_stats(project_id):
    """Statistiques spécifiques à un projet"""
    project = Project.query.get_or_404(project_id)
    
    # Vérifier les droits
    if project.farmer_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Non autorisé'}), 403
    
    # Vues du projet
    views = AnalyticsEvent.query.filter_by(
        project_id=project_id,
        event_type='project_view'
    ).count()
    
    # Contributions
    contributions = Contribution.query.filter_by(
        project_id=project_id,
        status='completed'
    ).all()
    
    # Trafic par source
    traffic_sources = db.session.query(
        AnalyticsEvent.referrer,
        db.func.count(AnalyticsEvent.id)
    ).filter(
        AnalyticsEvent.project_id == project_id
    ).group_by(AnalyticsEvent.referrer).all()
    
    return jsonify({
        'project_id': project_id,
        'project_title': project.title,
        'views': views,
        'contributions_count': len(contributions),
        'total_raised': float(project.amount_raised),
        'conversion_rate': round(len(contributions) / views * 100, 2) if views > 0 else 0,
        'traffic_sources': [
            {'source': s[0] or 'direct', 'count': s[1]} 
            for s in traffic_sources
        ]
    }), 200