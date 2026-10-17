"""
Routes pour les projets
"""

from datetime import datetime
from app.models.user import utc_now
from flask import request, jsonify, current_app, Blueprint
from flask_login import login_required, current_user
from app.api import api_bp
from app.models import Project, Contribution, HarvestUpdate, User
from app.extensions import db
from app.utils.decorators import farmer_required, admin_required
from app.utils.validators import validate_slug
from app.utils.storage import upload_image, delete_image


project_bp = Blueprint('projects', __name__, url_prefix='/projects')


@project_bp.route('', methods=['GET'])
def list_projects():
    """
    Liste tous les projets publiés
    ---
    parameters:
      - name: page
        in: query
        type: integer
      - name: per_page
        in: query
        type: integer
      - name: category
        in: query
        type: string
      - name: department
        in: query
        type: string
      - name: status
        in: query
        type: string
      - name: sort
        in: query
        type: string
        enum: [newest, popular, ending, funded]
      - name: search
        in: query
        type: string
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 12, type=int)
    category = request.args.get('category')
    department = request.args.get('department')
    status = request.args.get('status', 'published')
    sort = request.args.get('sort', 'newest')
    search = request.args.get('search')
    
    query = Project.query
    
    if status:
        query = query.filter_by(status=status, is_published=True)
    
    if category:
        query = query.filter_by(category=category)
    
    if department:
        query = query.filter_by(department=department)
    
    if search:
        query = query.filter(
            Project.title.ilike(f'%{search}%') | 
            Project.description.ilike(f'%{search}%')
        )
    
    # Tri
    if sort == 'newest':
        query = query.order_by(Project.created_at.desc())
    elif sort == 'popular':
        query = query.order_by(Project.investor_count.desc())
    elif sort == 'ending':
        query = query.filter(Project.deadline > utc_now()).order_by(Project.deadline.asc())
    elif sort == 'funded':
        query = query.filter_by(status='funded').order_by(Project.updated_at.desc())
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'projects': [p.to_dict() for p in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages,
        'filters': {
            'categories': [c[0] for c in db.session.query(Project.category.distinct()).all() if c[0]],
            'departments': [d[0] for d in db.session.query(Project.department.distinct()).all() if d[0]]
        }
    }), 200


@project_bp.route('/featured', methods=['GET'])
def get_featured_projects():
    """Récupère les projets à la une"""
    limit = request.args.get('limit', 6, type=int)
    
    projects = Project.query.filter_by(
        is_featured=True,
        is_published=True,
        status='published'
    ).order_by(
        Project.created_at.desc()
    ).limit(limit).all()
    
    return jsonify({
        'projects': [p.to_dict() for p in projects]
    }), 200


@project_bp.route('/stats', methods=['GET'])
def get_global_stats():
    """Statistiques globales des projets"""
    stats = {
        'total_projects': Project.query.filter_by(is_published=True).count(),
        'total_funded': Project.query.filter_by(status='funded').count(),
        'total_raised': float(db.session.query(db.func.sum(Project.amount_raised)).filter_by(is_published=True).scalar() or 0),
        'total_investors': Contribution.query.filter_by(status='completed').distinct('investor_id').count(),
        'active_projects': Project.query.filter_by(status='published', is_published=True).count(),
        'diaspora_contributions_percentage': 0  # Calculer
    }
    
    return jsonify(stats), 200


@project_bp.route('/<int:project_id>', methods=['GET'])
def get_project(project_id):
    """Récupère un projet par son ID"""
    project = Project.query.get_or_404(project_id)
    
    if not project.is_published and (not current_user.is_authenticated or 
        (current_user.id != project.farmer_id and not current_user.is_admin)):
        return jsonify({'error': 'Projet non disponible'}), 404
    
    include_updates = request.args.get('include_updates', 'false').lower() == 'true'
    
    return jsonify(project.to_dict(include_updates=include_updates)), 200


@project_bp.route('/slug/<slug>', methods=['GET'])
def get_project_by_slug(slug):
    """Récupère un projet par son slug"""
    project = Project.query.filter_by(slug=slug).first_or_404()
    
    if not project.is_published and (not current_user.is_authenticated or 
        (current_user.id != project.farmer_id and not current_user.is_admin)):
        return jsonify({'error': 'Projet non disponible'}), 404
    
    return jsonify(project.to_dict(include_updates=True)), 200


@project_bp.route('', methods=['POST'])
@login_required
@farmer_required
def create_project():
    """Crée un nouveau projet"""
    data = request.get_json()
    
    # Validation
    required_fields = ['title', 'description', 'amount_needed', 'deadline']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Le champ {field} est requis'}), 400
    
    # Création du projet
    project = Project(
        title=data['title'],
        description=data['description'],
        short_description=data.get('short_description'),
        location=data.get('location'),
        department=data.get('department'),
        commune=data.get('commune'),
        category=data.get('category'),
        amount_needed=data['amount_needed'],
        min_investment=data.get('min_investment', 10),
        max_investment=data.get('max_investment'),
        deadline=datetime.fromisoformat(data['deadline'].replace('Z', '+00:00')),
        farmer_id=current_user.id,
        currency=data.get('currency', 'HTG')
    )
    
    db.session.add(project)
    db.session.commit()
    
    # Calculer la commission estimée
    config = project.get_commission_config()
    project.estimated_platform_fee = config.calculate_commission(project.amount_needed)
    db.session.commit()
    
    return jsonify({
        'message': 'Projet créé avec succès',
        'project': project.to_dict()
    }), 201


@project_bp.route('/<int:project_id>', methods=['PUT'])
@login_required
def update_project(project_id):
    """Met à jour un projet"""
    project = Project.query.get_or_404(project_id)
    
    if project.farmer_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Vous n\'êtes pas autorisé à modifier ce projet'}), 403
    
    if project.status == 'funded':
        return jsonify({'error': 'Ce projet est déjà financé et ne peut plus être modifié'}), 400
    
    data = request.get_json()
    
    allowed_fields = ['title', 'description', 'short_description', 'location', 'department',
                      'commune', 'category', 'image_url', 'video_url', 'amount_needed',
                      'min_investment', 'max_investment', 'deadline']
    
    for field in allowed_fields:
        if field in data:
            if field == 'deadline' and data[field]:
                setattr(project, field, datetime.fromisoformat(data[field].replace('Z', '+00:00')))
            else:
                setattr(project, field, data[field])
    
    db.session.commit()
    
    return jsonify({
        'message': 'Projet mis à jour',
        'project': project.to_dict()
    }), 200


@project_bp.route('/<int:project_id>/publish', methods=['POST'])
@login_required
def publish_project(project_id):
    """Publie un projet"""
    project = Project.query.get_or_404(project_id)
    
    if project.farmer_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Non autorisé'}), 403
    
    if not project.image_url:
        return jsonify({'error': 'Veuillez ajouter une image avant de publier'}), 400
    
    if project.amount_needed <= 0:
        return jsonify({'error': 'Le montant nécessaire doit être supérieur à 0'}), 400
    
    project.publish()
    
    # Envoyer notification aux abonnés (à implémenter)
    # notify_subscribers(project)
    
    return jsonify({'message': 'Projet publié avec succès'}), 200


@project_bp.route('/<int:project_id>/unpublish', methods=['POST'])
@login_required
@admin_required
def unpublish_project(project_id):
    """Dépublie un projet (admin seulement)"""
    project = Project.query.get_or_404(project_id)
    
    project.is_published = False
    project.status = 'draft'
    db.session.commit()
    
    return jsonify({'message': 'Projet dépublié'}), 200


@project_bp.route('/<int:project_id>/feature', methods=['POST'])
@login_required
@admin_required
def feature_project(project_id):
    """Met un projet à la une (admin seulement)"""
    project = Project.query.get_or_404(project_id)
    project.is_featured = True
    db.session.commit()
    
    return jsonify({'message': 'Projet ajouté à la une'}), 200


@project_bp.route('/<int:project_id>/unfeature', methods=['POST'])
@login_required
@admin_required
def unfeature_project(project_id):
    """Retire un projet de la une (admin seulement)"""
    project = Project.query.get_or_404(project_id)
    project.is_featured = False
    db.session.commit()
    
    return jsonify({'message': 'Projet retiré de la une'}), 200


@project_bp.route('/<int:project_id>/contributions', methods=['GET'])
def get_project_contributions(project_id):
    """Récupère les contributions d'un projet"""
    project = Project.query.get_or_404(project_id)
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    query = Contribution.query.filter_by(
        project_id=project_id,
        status='completed'
    ).order_by(Contribution.created_at.desc())
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'contributions': [c.to_dict() for c in pagination.items],
        'total': pagination.total,
        'total_amount': float(project.amount_raised),
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    }), 200


@project_bp.route('/<int:project_id>/updates', methods=['GET'])
def get_project_updates(project_id):
    """Récupère les mises à jour d'un projet"""
    project = Project.query.get_or_404(project_id)
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    pagination = project.updates.filter_by(
        is_published=True
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'updates': [u.to_dict() for u in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    }), 200


@project_bp.route('/<int:project_id>/updates', methods=['POST'])
@login_required
def create_project_update(project_id):
    """Crée une mise à jour pour un projet"""
    project = Project.query.get_or_404(project_id)
    
    if project.farmer_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Non autorisé'}), 403
    
    data = request.get_json()
    
    if not data.get('title') or not data.get('content'):
        return jsonify({'error': 'Titre et contenu requis'}), 400
    
    update = HarvestUpdate(
        project_id=project_id,
        title=data['title'],
        content=data['content'],
        update_type=data.get('update_type', 'general'),
        image_url=data.get('image_url'),
        is_important=data.get('is_important', False)
    )
    
    db.session.add(update)
    db.session.commit()
    
    # Envoyer notification aux contributeurs si important
    if update.is_important:
        # send_notification_to_backers(project, update)
        pass
    
    return jsonify({
        'message': 'Mise à jour créée',
        'update': update.to_dict()
    }), 201


@project_bp.route('/categories', methods=['GET'])
def get_categories():
    """Récupère toutes les catégories disponibles"""
    categories = db.session.query(
        Project.category,
        db.func.count(Project.id).label('count')
    ).filter_by(
        is_published=True
    ).group_by(
        Project.category
    ).all()
    
    return jsonify({
        'categories': [
            {'name': c[0], 'count': c[1]} 
            for c in categories if c[0]
        ]
    }), 200


@project_bp.route('/departments', methods=['GET'])
def get_departments():
    """Récupère tous les départements disponibles"""
    departments = db.session.query(
        Project.department,
        db.func.count(Project.id).label('count')
    ).filter_by(
        is_published=True
    ).group_by(
        Project.department
    ).all()
    
    return jsonify({
        'departments': [
            {'name': d[0], 'count': d[1]} 
            for d in departments if d[0]
        ]
    }), 200