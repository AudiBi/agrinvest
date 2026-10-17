"""
Routes d'administration
"""

from app.models.user import utc_now
from flask import request, jsonify, Blueprint
from flask_login import login_required, current_user
from app.api import api_bp
from app.models import User, Project, Contribution, PlatformEarning
from app.extensions import db
from app.utils.decorators import admin_required
from app.utils.stats import get_platform_stats


admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/stats', methods=['GET'])
@login_required
@admin_required
def get_stats():
    """Statistiques globales de la plateforme"""
    stats = get_platform_stats()
    
    return jsonify(stats), 200


@admin_bp.route('/users', methods=['GET'])
@login_required
@admin_required
def list_all_users():
    """Liste tous les utilisateurs avec filtres"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    role = request.args.get('role')
    is_verified = request.args.get('is_verified')
    is_active = request.args.get('is_active')
    search = request.args.get('search')
    
    query = User.query
    
    if role:
        query = query.filter_by(role=role)
    if is_verified is not None:
        query = query.filter_by(is_verified=is_verified.lower() == 'true')
    if is_active is not None:
        query = query.filter_by(is_active=is_active.lower() == 'true')
    if search:
        query = query.filter(
            User.name.ilike(f'%{search}%') | 
            User.email.ilike(f'%{search}%')
        )
    
    pagination = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'users': [u.to_dict(include_email=True) for u in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    }), 200


@admin_bp.route('/users/<int:user_id>/verify', methods=['POST'])
@login_required
@admin_required
def verify_user(user_id):
    """Vérifie un utilisateur"""
    user = User.query.get_or_404(user_id)
    user.is_verified = True
    user.email_verified_at = utc_now()
    db.session.commit()
    
    return jsonify({'message': 'Utilisateur vérifié'}), 200


@admin_bp.route('/users/<int:user_id>/approve-ambassador', methods=['POST'])
@login_required
@admin_required
def approve_ambassador(user_id):
    """Accorde le rôle d'ambassadeur à un investisseur de la diaspora"""
    user = User.query.get_or_404(user_id)
    if user.role == 'ambassador':
        return jsonify({'message': 'Déjà ambassadeur'}), 200
    if user.role != 'investor' or not user.is_diaspora:
        return jsonify({'error': 'Seul un investisseur de la diaspora peut devenir ambassadeur'}), 409
    user.role = 'ambassador'
    db.session.commit()
    return jsonify({'message': 'Rôle ambassadeur accordé'}), 200


@admin_bp.route('/users/<int:user_id>/ban', methods=['POST'])
@login_required
@admin_required
def ban_user(user_id):
    """Bannit un utilisateur"""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        return jsonify({'error': 'Vous ne pouvez pas vous bannir vous-même'}), 400
    
    user.is_active = False
    db.session.commit()
    
    return jsonify({'message': 'Utilisateur banni'}), 200


@admin_bp.route('/users/<int:user_id>/unban', methods=['POST'])
@login_required
@admin_required
def unban_user(user_id):
    """Débannit un utilisateur"""
    user = User.query.get_or_404(user_id)
    user.is_active = True
    db.session.commit()
    
    return jsonify({'message': 'Utilisateur débanni'}), 200


@admin_bp.route('/projects/pending', methods=['GET'])
@login_required
@admin_required
def get_pending_projects():
    """Récupère les projets en attente de validation"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    projects = Project.query.filter_by(
        status='pending',
        is_published=False
    ).order_by(Project.created_at.asc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'projects': [p.to_dict() for p in projects.items],
        'total': projects.total,
        'page': page,
        'per_page': per_page,
        'pages': projects.pages
    }), 200


@admin_bp.route('/projects/<int:project_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_project(project_id):
    """Approuve un projet pour publication"""
    project = Project.query.get_or_404(project_id)

    # Un projet déjà publié, financé ou clos ne doit pas repasser en « published »
    if project.status not in ('pending', 'draft'):
        return jsonify({'error': f'Un projet « {project.status} » ne peut pas être approuvé'}), 409

    project.is_verified = True
    project.publish()
    
    # Notifier l'agriculteur
    # send_project_approved_notification(project)
    
    return jsonify({'message': 'Projet approuvé'}), 200


@admin_bp.route('/projects/<int:project_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_project(project_id):
    """Rejette un projet"""
    project = Project.query.get_or_404(project_id)
    
    data = request.get_json(silent=True) or {}
    reason = data.get('reason', '')

    if project.status not in ('pending', 'draft'):
        return jsonify({'error': f'Un projet « {project.status} » ne peut pas être rejeté'}), 409

    project.status = 'draft'
    project.is_published = False
    db.session.commit()
    
    # Notifier l'agriculteur avec la raison
    # send_project_rejected_notification(project, reason)
    
    return jsonify({'message': 'Projet rejeté'}), 200


@admin_bp.route('/dashboard', methods=['GET'])
@login_required
@admin_required
def admin_dashboard():
    """Tableau de bord administrateur"""
    
    # Statistiques rapides
    stats = {
        'total_users': User.query.count(),
        'total_farmers': User.query.filter_by(role='farmer').count(),
        'total_investors': User.query.filter_by(role='investor').count(),
        'total_projects': Project.query.count(),
        'published_projects': Project.query.filter_by(is_published=True).count(),
        'funded_projects': Project.query.filter_by(status='funded').count(),
        'total_contributions': Contribution.query.filter_by(status='completed').count(),
        'total_raised_htg': float(Contribution.query.filter_by(status='completed').with_entities(
            db.func.sum(Contribution.amount_htg)).scalar() or 0),
        'pending_projects': Project.query.filter_by(status='pending', is_published=False).count(),
        'pending_contributions': Contribution.query.filter_by(status='pending').count(),
        'platform_earnings_htg': float(PlatformEarning.query.filter_by(
            status='paid').with_entities(db.func.sum(PlatformEarning.commission_amount_htg)).scalar() or 0)
    }
    
    # Dernières activités
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    recent_projects = Project.query.order_by(Project.created_at.desc()).limit(5).all()
    recent_contributions = Contribution.query.order_by(Contribution.created_at.desc()).limit(5).all()
    
    return jsonify({
        'stats': stats,
        'recent_users': [u.to_dict() for u in recent_users],
        'recent_projects': [p.to_dict() for p in recent_projects],
        'recent_contributions': [c.to_dict() for c in recent_contributions]
    }), 200