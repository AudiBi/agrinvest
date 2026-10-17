"""
Routes pour l'analytique
"""

from flask import request, jsonify, Blueprint
from flask_login import login_required, current_user
from app.api import api_bp
from app.models import AnalyticsEvent, User, Project, Contribution
from app.extensions import db
from app.utils.decorators import admin_required, rate_limit


analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')


@analytics_bp.route('/track', methods=['POST'])
@rate_limit(limit=120, per=60)  # endpoint public : on borne l'écriture en base par IP
def track_event():
    """Enregistre un événement analytique"""
    data = request.get_json(silent=True) or {}
    if not isinstance(data.get('event_type'), str) or not data['event_type'] or len(data['event_type']) > 50:
        return jsonify({'error': 'event_type requis (50 caractères max)'}), 400
    
    event = AnalyticsEvent(
        event_type=data['event_type'],
        user_id=current_user.id if current_user.is_authenticated else None,
        page_url=data.get('page_url'),
        referrer=data.get('referrer'),
        user_agent=request.headers.get('User-Agent'),
        ip_address=request.remote_addr,
        event_data=data.get('event_data'),
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
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Compter les événements par type
    page_views = AnalyticsEvent.query.filter_by(event_type='page_view').count()
    contribution_starts = AnalyticsEvent.query.filter_by(event_type='contribution_start').count()
    contribution_completes = AnalyticsEvent.query.filter_by(event_type='contribution_complete').count()
    
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
    days = request.args.get('days', 30, type=int)
    
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