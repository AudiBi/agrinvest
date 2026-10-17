"""
Routes pour les projets
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from app.models.user import utc_now
from flask import request, jsonify, current_app, Blueprint
from flask_login import login_required, current_user
from app.api import api_bp
from app.models import Project, Contribution, HarvestUpdate, User
from app.extensions import db
from app.utils.decorators import farmer_required, admin_required
from app.utils.validators import validate_slug, validate_url
from app.utils.storage import upload_image, delete_image


project_bp = Blueprint('projects', __name__, url_prefix='/projects')

MAX_PER_PAGE = 100
PUBLIC_STATUSES = ('published', 'funded', 'expired')
# Statuts à partir desquels les montants et l'échéance ne sont plus modifiables par l'agriculteur
LOCKED_FOR_FARMER = ('published', 'funded', 'expired', 'cancelled')
MONEY_FIELDS = ('amount_needed', 'min_investment', 'max_investment', 'deadline', 'currency')


def _per_page(default):
    return max(1, min(request.args.get('per_page', default, type=int), MAX_PER_PAGE))


def _can_view(project):
    """Un projet non publié n'est visible que de son propriétaire et des administrateurs."""
    return project.is_published or (
        current_user.is_authenticated and (current_user.id == project.farmer_id or current_user.is_admin))


def _parse_deadline(value):
    deadline = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if deadline.tzinfo:  # colonnes DateTime naïves, en UTC
        deadline = deadline.astimezone(timezone.utc).replace(tzinfo=None)
    return deadline


def _clean_fields(data, current=None):
    """Valide et normalise les champs d'un projet. Lève ValueError avec un message lisible.

    `current` : projet existant (mise à jour partielle) ; None pour une création.
    """
    cleaned = {}

    def money(name, allow_none=False):
        value = data[name]
        if value is None and allow_none:
            return None
        try:
            amount = Decimal(str(value))
        except InvalidOperation:
            raise ValueError(f'{name} invalide')
        if not amount.is_finite() or amount <= 0 or amount >= Decimal('1e10'):
            raise ValueError(f'{name} doit être un montant strictement positif')
        return amount

    for name in ('amount_needed', 'min_investment'):
        if name in data:
            cleaned[name] = money(name)
    if 'max_investment' in data:
        cleaned['max_investment'] = money('max_investment', allow_none=True)
    if 'deadline' in data and data['deadline']:
        try:
            cleaned['deadline'] = _parse_deadline(data['deadline'])
        except (ValueError, TypeError, AttributeError):
            raise ValueError('deadline invalide (format ISO 8601 attendu)')
        if current is None and cleaned['deadline'] <= utc_now().replace(tzinfo=None):
            raise ValueError('deadline doit être dans le futur')
    if 'currency' in data:
        currency = str(data['currency']).upper()
        if currency not in current_app.config['SUPPORTED_CURRENCIES']:
            raise ValueError(f'Devise non supportée : {currency}')
        cleaned['currency'] = currency
    for name in ('image_url', 'video_url'):
        if data.get(name):
            if not validate_url(data[name]):
                raise ValueError(f'{name} doit être une URL http(s) valide')
            cleaned[name] = data[name]
    for name in ('title', 'description', 'short_description', 'location', 'department', 'commune', 'category'):
        if name in data:
            if data[name] is not None and not isinstance(data[name], str):
                raise ValueError(f'{name} doit être du texte')
            cleaned[name] = data[name]
    if cleaned.get('title') is not None and not 3 <= len(cleaned['title'].strip()) <= 200:
        raise ValueError('title doit contenir entre 3 et 200 caractères')

    needed = cleaned.get('amount_needed', current.amount_needed if current else None)
    minimum = cleaned.get('min_investment', current.min_investment if current else Decimal('10'))
    maximum = cleaned.get('max_investment', current.max_investment if current else None)
    if needed is not None and minimum is not None and minimum > needed:
        raise ValueError('min_investment ne peut pas dépasser amount_needed')
    if maximum is not None and minimum is not None and maximum < minimum:
        raise ValueError('max_investment ne peut pas être inférieur à min_investment')
    if current is not None and 'amount_needed' in cleaned and cleaned['amount_needed'] < (current.amount_raised or 0):
        raise ValueError('amount_needed ne peut pas être inférieur au montant déjà collecté')
    return cleaned


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
    per_page = _per_page(12)
    category = request.args.get('category')
    department = request.args.get('department')
    status = request.args.get('status') or 'published'
    sort = request.args.get('sort', 'newest')
    search = request.args.get('search')

    if status not in PUBLIC_STATUSES:
        return jsonify({'error': f'status doit être parmi : {", ".join(PUBLIC_STATUSES)}'}), 400

    # Jamais de projet non publié dans la liste publique (même avec ?status= vide)
    query = Project.query.filter_by(status=status, is_published=True)
    
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
        'total_investors': db.session.query(db.func.count(db.func.distinct(Contribution.investor_id))).filter(
            Contribution.status == 'completed').scalar() or 0,
        'active_projects': Project.query.filter_by(status='published', is_published=True).count(),
        'diaspora_contributions_percentage': 0  # Calculer
    }
    
    return jsonify(stats), 200


@project_bp.route('/<int:project_id>', methods=['GET'])
def get_project(project_id):
    """Récupère un projet par son ID"""
    project = Project.query.get_or_404(project_id)

    if not _can_view(project):
        return jsonify({'error': 'Projet non disponible'}), 404

    include_updates = request.args.get('include_updates', 'false').lower() == 'true'
    
    return jsonify(project.to_dict(include_updates=include_updates)), 200


@project_bp.route('/slug/<slug>', methods=['GET'])
def get_project_by_slug(slug):
    """Récupère un projet par son slug"""
    project = Project.query.filter_by(slug=slug).first_or_404()

    if not _can_view(project):
        return jsonify({'error': 'Projet non disponible'}), 404
    
    return jsonify(project.to_dict(include_updates=True)), 200


@project_bp.route('', methods=['POST'])
@login_required
@farmer_required
def create_project():
    """Crée un nouveau projet"""
    data = request.get_json(silent=True) or {}

    # Validation
    required_fields = ['title', 'description', 'amount_needed', 'deadline']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Le champ {field} est requis'}), 400

    try:
        fields = _clean_fields(data)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    # Création du projet
    project = Project(
        title=fields['title'],
        description=fields['description'],
        short_description=fields.get('short_description'),
        location=fields.get('location'),
        department=fields.get('department'),
        commune=fields.get('commune'),
        category=fields.get('category'),
        image_url=fields.get('image_url'),
        video_url=fields.get('video_url'),
        amount_needed=fields['amount_needed'],
        min_investment=fields.get('min_investment', Decimal('10')),
        max_investment=fields.get('max_investment'),
        deadline=fields['deadline'],
        farmer_id=current_user.id,
        currency=fields.get('currency', 'HTG')
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

    data = request.get_json(silent=True) or {}

    allowed_fields = ['title', 'description', 'short_description', 'location', 'department',
                      'commune', 'category', 'image_url', 'video_url', 'amount_needed',
                      'min_investment', 'max_investment', 'deadline', 'currency']
    data = {k: v for k, v in data.items() if k in allowed_fields}

    # Des investisseurs ont engagé de l'argent sur ces conditions : seul un administrateur peut les modifier
    locked = [f for f in MONEY_FIELDS if f in data]
    if locked and not current_user.is_admin and (
            project.status in LOCKED_FOR_FARMER or (project.amount_raised or 0) > 0):
        return jsonify({'error': f'Champs non modifiables une fois le projet publié : {", ".join(locked)}'}), 403

    try:
        fields = _clean_fields(data, current=project)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    for field, value in fields.items():
        setattr(project, field, value)

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
    
    if project.status not in ('draft', 'pending'):
        return jsonify({'error': f'Un projet « {project.status} » ne peut pas être publié'}), 409

    if not project.image_url:
        return jsonify({'error': 'Veuillez ajouter une image avant de publier'}), 400

    if project.amount_needed <= 0:
        return jsonify({'error': 'Le montant nécessaire doit être supérieur à 0'}), 400

    if project.is_expired:
        return jsonify({'error': "La date limite est dépassée : modifiez la deadline avant de publier"}), 400

    if not project.submit_for_publication():
        return jsonify({'message': 'Projet soumis : il sera publié après validation par un administrateur'}), 202

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
    if not _can_view(project):
        return jsonify({'error': 'Projet non disponible'}), 404

    page = request.args.get('page', 1, type=int)
    per_page = _per_page(20)

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
    if not _can_view(project):
        return jsonify({'error': 'Projet non disponible'}), 404

    page = request.args.get('page', 1, type=int)
    per_page = _per_page(10)

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
    
    data = request.get_json(silent=True) or {}

    if not data.get('title') or not data.get('content'):
        return jsonify({'error': 'Titre et contenu requis'}), 400
    if data.get('image_url') and not validate_url(data['image_url']):
        return jsonify({'error': 'image_url doit être une URL http(s) valide'}), 400
    
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