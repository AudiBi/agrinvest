# app/routes/admin.py
"""
Routes d'administration pour AgriInvest Haïti
Gère le panel administrateur, la modération et les statistiques
"""

from app.models.training import TrainingProgress
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime, timedelta
from decimal import Decimal

from app.models import User, Project, Contribution, HarvestUpdate, Training
from app.models import PlatformEarning, CEOPayout, WeatherAlert
from app.models.enums import ProjectStatus, ContributionStatus, UserRole
from app.extensions import db


# Création du blueprint
admin_bp = Blueprint('admin', __name__)


# ============================================================================
# DÉCORATEURS
# ============================================================================

def admin_required(f):
    """Décorateur pour vérifier que l'utilisateur est administrateur"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Veuillez vous connecter', 'warning')
            return redirect(url_for('auth.login'))
        
        if not current_user.is_admin:
            flash('Accès non autorisé. Zone administrateur uniquement.', 'danger')
            return redirect(url_for('main.home'))
        
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# TABLEAU DE BORD PRINCIPAL
# ============================================================================

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Tableau de bord administrateur principal"""
    
    # Statistiques générales
    stats = {
        # Utilisateurs
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(is_active=True).count(),
        'total_farmers': User.query.filter_by(role=UserRole.FARMER).count(),
        'total_investors': User.query.filter_by(role=UserRole.INVESTOR).count(),
        'new_users_today': User.query.filter(
            User.created_at >= datetime.now().replace(hour=0, minute=0, second=0)
        ).count(),
        'verified_users': User.query.filter_by(is_verified=True).count(),
        
        # Projets
        'total_projects': Project.query.count(),
        'published_projects': Project.query.filter_by(is_published=True).count(),
        'funded_projects': Project.query.filter_by(status=ProjectStatus.FUNDED).count(),
        'pending_projects': Project.query.filter_by(status=ProjectStatus.PENDING).count(),
        'draft_projects': Project.query.filter_by(status=ProjectStatus.DRAFT).count(),
        'expired_projects': Project.query.filter_by(status=ProjectStatus.EXPIRED).count(),
        
        # Contributions
        'total_contributions': Contribution.query.filter_by(status=ContributionStatus.COMPLETED).count(),
        'total_amount': db.session.query(db.func.sum(Contribution.amount_htg)).filter_by(
            status=ContributionStatus.COMPLETED
        ).scalar() or 0,
        'pending_contributions': Contribution.query.filter_by(status=ContributionStatus.PENDING).count(),
        
        # Finances plateforme
        'platform_earnings': db.session.query(db.func.sum(PlatformEarning.commission_amount_htg)).filter_by(
            status='paid'
        ).scalar() or 0,
        'pending_payouts': db.session.query(db.func.sum(CEOPayout.payout_amount)).filter_by(
            status='pending'
        ).scalar() or 0,
        
        # Formations
        'total_trainings': Training.query.filter_by(is_published=True).count(),
        'completed_trainings': TrainingProgress.query.filter_by(status='completed').count(),
    }
    
    # Évolution des inscriptions (7 derniers jours)
    daily_users = []
    for i in range(7):
        day = datetime.now().replace(hour=0, minute=0, second=0) - timedelta(days=i)
        next_day = day + timedelta(days=1)
        count = User.query.filter(
            User.created_at >= day,
            User.created_at < next_day
        ).count()
        daily_users.append({
            'date': day.strftime('%d/%m'),
            'count': count
        })
    
    # Derniers utilisateurs inscrits
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    
    # Dernières contributions
    recent_contributions = Contribution.query.order_by(
        Contribution.created_at.desc()
    ).limit(10).all()
    
    # Projets en attente de validation
    pending_projects_list = Project.query.filter_by(
        status=ProjectStatus.PENDING,
        is_published=False
    ).order_by(Project.created_at.asc()).limit(10).all()
    
    return render_template('admin/dashboard.html',
                         stats=stats,
                         daily_users=daily_users,
                         recent_users=recent_users,
                         recent_contributions=recent_contributions,
                         pending_projects=pending_projects_list)


# ============================================================================
# GESTION DES UTILISATEURS
# ============================================================================

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    """Liste des utilisateurs avec filtres"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    role = request.args.get('role')
    search = request.args.get('search', '')
    status = request.args.get('status', 'all')
    
    query = User.query
    
    if role:
        query = query.filter_by(role=role)
    
    if search:
        query = query.filter(
            User.name.ilike(f'%{search}%') | 
            User.email.ilike(f'%{search}%')
        )
    
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)
    elif status == 'verified':
        query = query.filter_by(is_verified=True)
    elif status == 'unverified':
        query = query.filter_by(is_verified=False)
    
    users_pagination = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Statistiques pour les filtres
    stats = {
        'total': User.query.count(),
        'active': User.query.filter_by(is_active=True).count(),
        'inactive': User.query.filter_by(is_active=False).count(),
        'verified': User.query.filter_by(is_verified=True).count(),
        'unverified': User.query.filter_by(is_verified=False).count(),
        'farmers': User.query.filter_by(role=UserRole.FARMER).count(),
        'investors': User.query.filter_by(role=UserRole.INVESTOR).count(),
        'admins': User.query.filter_by(is_admin=True).count()
    }
    
    return render_template('admin/users.html',
                         users=users_pagination,
                         stats=stats,
                         selected_role=role,
                         selected_status=status,
                         search_query=search)


@admin_bp.route('/users/<int:user_id>')
@login_required
@admin_required
def user_detail(user_id):
    """Détail d'un utilisateur"""
    user = User.query.get_or_404(user_id)
    
    # Contributions de l'utilisateur
    contributions = Contribution.query.filter_by(
        investor_id=user_id,
        status=ContributionStatus.COMPLETED
    ).order_by(Contribution.created_at.desc()).limit(50).all()
    
    # Projets de l'utilisateur (si agriculteur)
    projects = []
    if user.is_farmer:
        projects = Project.query.filter_by(farmer_id=user_id).order_by(
            Project.created_at.desc()
        ).all()
    
    return render_template('admin/user_detail.html',
                         user=user,
                         contributions=contributions,
                         projects=projects)


@admin_bp.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@login_required
@admin_required
def toggle_user_active(user_id):
    """Activer/Désactiver un utilisateur"""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('Vous ne pouvez pas désactiver votre propre compte', 'danger')
        return redirect(url_for('admin.user_detail', user_id=user_id))
    
    user.is_active = not user.is_active
    db.session.commit()
    
    status = "activé" if user.is_active else "désactivé"
    flash(f'Utilisateur {status} avec succès', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/users/<int:user_id>/toggle-verified', methods=['POST'])
@login_required
@admin_required
def toggle_user_verified(user_id):
    """Vérifier un utilisateur"""
    user = User.query.get_or_404(user_id)
    
    user.is_verified = not user.is_verified
    if user.is_verified and not user.email_verified_at:
        from app.utils.timezone import utc_now
        user.email_verified_at = utc_now()
    
    db.session.commit()
    
    status = "vérifié" if user.is_verified else "non vérifié"
    flash(f'Utilisateur marqué comme {status}', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/users/<int:user_id>/make-admin', methods=['POST'])
@login_required
@admin_required
def make_admin(user_id):
    """Promouvoir un utilisateur en administrateur"""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('Action non nécessaire', 'info')
        return redirect(url_for('admin.user_detail', user_id=user_id))
    
    user.is_admin = not user.is_admin
    db.session.commit()
    
    status = "administrateur" if user.is_admin else "utilisateur standard"
    flash(f'Utilisateur promu {status}', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """Supprimer un utilisateur (soft delete)"""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('Vous ne pouvez pas supprimer votre propre compte', 'danger')
        return redirect(url_for('admin.user_detail', user_id=user_id))
    
    # Soft delete - désactiver seulement
    user.is_active = False
    user.email = f"deleted_{user.id}@{user.email.split('@')[-1]}"
    db.session.commit()
    
    flash('Utilisateur supprimé avec succès', 'success')
    return redirect(url_for('admin.users'))


# ============================================================================
# GESTION DES PROJETS
# ============================================================================

@admin_bp.route('/projects')
@login_required
@admin_required
def projects():
    """Liste des projets avec filtres"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
    search = request.args.get('search', '')
    
    query = Project.query
    
    if status:
        query = query.filter_by(status=status)
    
    if search:
        query = query.filter(
            Project.title.ilike(f'%{search}%') |
            Project.description.ilike(f'%{search}%')
        )
    
    projects_pagination = query.order_by(Project.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Statistiques
    stats = {
        'total': Project.query.count(),
        'published': Project.query.filter_by(is_published=True).count(),
        'funded': Project.query.filter_by(status=ProjectStatus.FUNDED).count(),
        'pending': Project.query.filter_by(status=ProjectStatus.PENDING).count(),
        'draft': Project.query.filter_by(status=ProjectStatus.DRAFT).count(),
        'expired': Project.query.filter_by(status=ProjectStatus.EXPIRED).count(),
        'cancelled': Project.query.filter_by(status=ProjectStatus.CANCELLED).count()
    }
    
    return render_template('admin/projects.html',
                         projects=projects_pagination,
                         stats=stats,
                         selected_status=status,
                         search_query=search)


@admin_bp.route('/projects/<int:project_id>')
@login_required
@admin_required
def project_detail(project_id):
    """Détail d'un projet pour l'admin"""
    project = Project.query.get_or_404(project_id)
    
    contributions = Contribution.query.filter_by(
        project_id=project_id,
        status=ContributionStatus.COMPLETED
    ).order_by(Contribution.created_at.desc()).all()
    
    return render_template('admin/project_detail.html',
                         project=project,
                         contributions=contributions)


@admin_bp.route('/projects/<int:project_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_project(project_id):
    """Approuver un projet en attente"""
    project = Project.query.get_or_404(project_id)
    
    if project.status != ProjectStatus.PENDING:
        flash('Ce projet n\'est pas en attente de validation', 'warning')
        return redirect(url_for('admin.project_detail', project_id=project_id))
    
    project.status = ProjectStatus.PUBLISHED
    project.is_published = True
    project.published_at = datetime.now()
    project.is_verified = True
    
    db.session.commit()
    
    # Notifier l'agriculteur
    # send_project_approved_notification(project)
    
    flash('Projet approuvé et publié avec succès', 'success')
    return redirect(url_for('admin.projects'))


@admin_bp.route('/projects/<int:project_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_project(project_id):
    """Rejeter un projet en attente"""
    project = Project.query.get_or_404(project_id)
    
    if project.status != ProjectStatus.PENDING:
        flash('Ce projet n\'est pas en attente de validation', 'warning')
        return redirect(url_for('admin.project_detail', project_id=project_id))
    
    reason = request.form.get('reason', '')
    
    project.status = ProjectStatus.DRAFT
    project.is_published = False
    
    db.session.commit()
    
    # Notifier l'agriculteur avec la raison
    # send_project_rejected_notification(project, reason)
    
    flash('Projet rejeté', 'warning')
    return redirect(url_for('admin.projects'))


@admin_bp.route('/projects/<int:project_id>/feature', methods=['POST'])
@login_required
@admin_required
def feature_project(project_id):
    """Mettre un projet en vedette"""
    project = Project.query.get_or_404(project_id)
    
    project.is_featured = not project.is_featured
    db.session.commit()
    
    status = "à la une" if project.is_featured else "retiré de la une"
    flash(f'Projet {status}', 'success')
    return redirect(url_for('admin.project_detail', project_id=project_id))


@admin_bp.route('/projects/<int:project_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_project(project_id):
    """Supprimer un projet"""
    project = Project.query.get_or_404(project_id)
    
    # Soft delete
    project.is_published = False
    project.status = ProjectStatus.CANCELLED
    
    db.session.commit()
    
    flash('Projet supprimé avec succès', 'success')
    return redirect(url_for('admin.projects'))


# ============================================================================
# STATISTIQUES ET RAPPORTS
# ============================================================================

@admin_bp.route('/stats')
@login_required
@admin_required
def stats():
    """Page des statistiques détaillées"""
    
    # Statistiques mensuelles (12 derniers mois)
    monthly_stats = []
    for i in range(12):
        month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0) - timedelta(days=30*i)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(microseconds=1)
        
        users_count = User.query.filter(
            User.created_at.between(month_start, month_end)
        ).count()
        
        projects_count = Project.query.filter(
            Project.created_at.between(month_start, month_end)
        ).count()
        
        contributions_count = Contribution.query.filter(
            Contribution.created_at.between(month_start, month_end),
            Contribution.status == ContributionStatus.COMPLETED
        ).count()
        
        amount = db.session.query(db.func.sum(Contribution.amount_htg)).filter(
            Contribution.created_at.between(month_start, month_end),
            Contribution.status == ContributionStatus.COMPLETED
        ).scalar() or 0
        
        monthly_stats.append({
            'month': month_start.strftime('%b %Y'),
            'users': users_count,
            'projects': projects_count,
            'contributions': contributions_count,
            'amount': float(amount)
        })
    
    # Top projets
    top_projects = db.session.query(
        Project.title,
        db.func.sum(Contribution.amount_htg).label('total')
    ).join(
        Contribution, Contribution.project_id == Project.id
    ).filter(
        Contribution.status == ContributionStatus.COMPLETED
    ).group_by(
        Project.id
    ).order_by(
        db.func.sum(Contribution.amount_htg).desc()
    ).limit(10).all()
    
    # Top investisseurs
    top_investors = db.session.query(
        User.name,
        db.func.sum(Contribution.amount_htg).label('total')
    ).join(
        Contribution, Contribution.investor_id == User.id
    ).filter(
        Contribution.status == ContributionStatus.COMPLETED
    ).group_by(
        User.id
    ).order_by(
        db.func.sum(Contribution.amount_htg).desc()
    ).limit(10).all()
    
    return render_template('admin/stats.html',
                         monthly_stats=monthly_stats,
                         top_projects=top_projects,
                         top_investors=top_investors)


# ============================================================================
# CONFIGURATION DE LA PLATEFORME
# ============================================================================

@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def settings():
    """Paramètres de la plateforme"""
    if request.method == 'POST':
        # Mettre à jour les paramètres
        from app.utils.config import set_config_value
        
        set_config_value('APP_NAME', request.form.get('app_name'))
        set_config_value('COMMISSION_RATE', float(request.form.get('commission_rate', 3.0)))
        set_config_value('MIN_CONTRIBUTION', int(request.form.get('min_contribution', 100)))
        set_config_value('MAX_CONTRIBUTION', int(request.form.get('max_contribution', 10000000)))
        set_config_value('CONTACT_EMAIL', request.form.get('contact_email'))
        set_config_value('SUPPORT_EMAIL', request.form.get('support_email'))
        
        flash('Paramètres mis à jour avec succès', 'success')
        return redirect(url_for('admin.settings'))
    
    from app.utils.config import get_platform_settings
    settings = get_platform_settings()
    
    return render_template('admin/settings.html', settings=settings)