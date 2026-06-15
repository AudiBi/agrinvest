"""
Routes pour les utilisateurs
"""

from app.models.contribution import Contribution
from flask import request, jsonify, Blueprint
from flask_login import login_required, current_user
from app.api import api_bp
from app.models import Project, User
from app.extensions import db
from app.utils.decorators import admin_required, farmer_required


user_bp = Blueprint('users', __name__, url_prefix='/users')


@user_bp.route('', methods=['GET'])
@login_required
@admin_required
def list_users():
    """
    Liste tous les utilisateurs (admin seulement)
    ---
    parameters:
      - name: page
        in: query
        type: integer
      - name: per_page
        in: query
        type: integer
      - name: role
        in: query
        type: string
      - name: country
        in: query
        type: string
      - name: search
        in: query
        type: string
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    role = request.args.get('role')
    country = request.args.get('country')
    search = request.args.get('search')
    
    query = User.query
    
    if role:
        query = query.filter_by(role=role)
    if country:
        query = query.filter_by(country=country)
    if search:
        query = query.filter(
            User.name.ilike(f'%{search}%') | 
            User.email.ilike(f'%{search}%')
        )
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'users': [u.to_dict() for u in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    }), 200


@user_bp.route('/<int:user_id>', methods=['GET'])
@login_required
def get_user(user_id):
    """Récupère un utilisateur par son ID"""
    if user_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Accès non autorisé'}), 403
    
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict(include_email=current_user.is_admin)), 200


@user_bp.route('/<int:user_id>', methods=['PUT'])
@login_required
def update_user(user_id):
    """Met à jour un utilisateur"""
    if user_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Accès non autorisé'}), 403
    
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    allowed_fields = ['name', 'phone', 'location', 'bio', 'avatar_url', 
                      'country', 'city', 'preferred_currency', 'preferred_language',
                      'diaspora_newsletter', 'sms_alerts_enabled', 'whatsapp_alerts_enabled']
    
    for field in allowed_fields:
        if field in data:
            setattr(user, field, data[field])
    
    if current_user.is_admin and 'role' in data:
        user.role = data['role']
    
    db.session.commit()
    
    return jsonify({
        'message': 'Utilisateur mis à jour',
        'user': user.to_dict()
    }), 200


@user_bp.route('/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_user(user_id):
    """Supprime un utilisateur (admin seulement)"""
    user = User.query.get_or_404(user_id)
    
    # Ne pas supprimer son propre compte
    if user.id == current_user.id:
        return jsonify({'error': 'Vous ne pouvez pas supprimer votre propre compte'}), 400
    
    user.is_active = False
    db.session.commit()
    
    return jsonify({'message': 'Utilisateur désactivé'}), 200


@user_bp.route('/<int:user_id>/contributions', methods=['GET'])
@login_required
def get_user_contributions(user_id):
    """Récupère les contributions d'un utilisateur"""
    if user_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Accès non autorisé'}), 403
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    user = User.query.get_or_404(user_id)
    pagination = user.contributions.filter_by(
        status='completed'
    ).order_by(
        Contribution.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'contributions': [c.to_dict() for c in pagination.items],
        'total': pagination.total,
        'total_invested': float(user.get_total_invested()),
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    }), 200


@user_bp.route('/<int:user_id>/projects', methods=['GET'])
@login_required
def get_user_projects(user_id):
    """Récupère les projets d'un utilisateur (agriculteur)"""
    if user_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Accès non autorisé'}), 403
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    user = User.query.get_or_404(user_id)
    
    if not user.is_farmer and not current_user.is_admin:
        return jsonify({'error': 'Cet utilisateur n\'est pas un agriculteur'}), 400
    
    pagination = user.projects.order_by(
        Project.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'projects': [p.to_dict() for p in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    }), 200


@user_bp.route('/stats', methods=['GET'])
@login_required
def get_user_stats():
    """Statistiques de l'utilisateur connecté"""
    stats = {
        'total_invested': float(current_user.get_total_invested()),
        'investments_count': current_user.contributions.filter_by(
            status='completed'
        ).count(),
        'projects_count': current_user.projects.count() if current_user.is_farmer else 0,
        'active_projects': current_user.projects.filter_by(
            status='published'
        ).count() if current_user.is_farmer else 0,
        'member_since': current_user.created_at.isoformat(),
        'is_diaspora': current_user.is_diaspora,
        'preferred_currency': current_user.preferred_currency
    }
    
    return jsonify(stats), 200


@user_bp.route('/dashboard', methods=['GET'])
@login_required
def get_dashboard():
    """Tableau de bord utilisateur"""
    
    if current_user.is_farmer:
        # Dashboard agriculteur
        projects = current_user.projects.all()
        total_raised = sum(p.amount_raised for p in projects)
        total_contributors = sum(p.investor_count for p in projects)
        
        dashboard = {
            'role': 'farmer',
            'stats': {
                'total_projects': len(projects),
                'total_raised': float(total_raised),
                'total_contributors': total_contributors,
                'active_projects': sum(1 for p in projects if p.status == 'published'),
                'funded_projects': sum(1 for p in projects if p.status == 'funded')
            },
            'recent_projects': [p.to_dict() for p in projects[:5]],
            'recent_contributions': [c.to_dict() for c in 
                Contribution.query.join(Project)
                .filter(Project.farmer_id == current_user.id)
                .order_by(Contribution.created_at.desc())
                .limit(10).all()]
        }
    
    else:
        # Dashboard investisseur
        contributions = current_user.contributions.filter_by(status='completed').all()
        total_invested = sum(c.amount_htg for c in contributions)
        
        dashboard = {
            'role': 'investor',
            'stats': {
                'total_invested': float(total_invested),
                'investments_count': len(contributions),
                'projects_supported': len(set(c.project_id for c in contributions)),
                'avg_investment': float(total_invested / len(contributions)) if contributions else 0
            },
            'recent_contributions': [c.to_dict() for c in contributions[:10]],
            'active_projects': [p.to_dict() for p in 
                Project.query.filter_by(status='published')
                .limit(6).all()]
        }
    
    return jsonify(dashboard), 200