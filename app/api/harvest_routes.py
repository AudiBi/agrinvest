"""
Routes pour les mises à jour de récolte
"""

from flask import request, jsonify, Blueprint
from flask_login import login_required, current_user
from app.api import api_bp
from app.models import HarvestUpdate, Project
from app.extensions import db


harvest_bp = Blueprint('harvest', __name__, url_prefix='/harvest-updates')


@harvest_bp.route('/projects/<int:project_id>', methods=['GET'])
def get_project_updates(project_id):
    """Récupère toutes les mises à jour d'un projet"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    project = Project.query.get_or_404(project_id)
    
    query = project.updates.filter_by(is_published=True)
    
    if request.args.get('important', 'false').lower() == 'true':
        query = query.filter_by(is_important=True)
    
    pagination = query.order_by(HarvestUpdate.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'updates': [u.to_dict() for u in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    }), 200


@harvest_bp.route('', methods=['POST'])
@login_required
def create_update():
    """Crée une mise à jour"""
    data = request.get_json()
    
    project = Project.query.get_or_404(data['project_id'])
    
    # Vérifier les droits
    if project.farmer_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Non autorisé'}), 403
    
    update = HarvestUpdate(
        project_id=project.id,
        title=data['title'],
        title_ht=data.get('title_ht'),
        content=data['content'],
        content_ht=data.get('content_ht'),
        update_type=data.get('update_type', 'general'),
        image_url=data.get('image_url'),
        video_url=data.get('video_url'),
        is_important=data.get('is_important', False),
        notify_investors=data.get('notify_investors', False)
    )
    
    db.session.add(update)
    db.session.commit()
    
    # Envoyer des notifications si demandé
    if update.notify_investors:
        # Envoyer email aux contributeurs
        # send_update_notification(update)
        pass
    
    return jsonify({
        'message': 'Mise à jour créée',
        'update': update.to_dict()
    }), 201


@harvest_bp.route('/<int:update_id>', methods=['GET'])
def get_update(update_id):
    """Récupère une mise à jour spécifique"""
    update = HarvestUpdate.query.get_or_404(update_id)
    
    # Vérifier si le projet est publié ou si l'utilisateur a le droit
    if not update.is_published and not current_user.is_authenticated:
        return jsonify({'error': 'Non disponible'}), 404
    
    if not update.is_published and \
       update.project.farmer_id != current_user.id and \
       not current_user.is_admin:
        return jsonify({'error': 'Non disponible'}), 404
    
    return jsonify(update.to_dict()), 200


@harvest_bp.route('/<int:update_id>', methods=['PUT'])
@login_required
def update_update(update_id):
    """Met à jour une mise à jour"""
    update = HarvestUpdate.query.get_or_404(update_id)
    
    if update.project.farmer_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Non autorisé'}), 403
    
    data = request.get_json()
    
    allowed_fields = ['title', 'title_ht', 'content', 'content_ht', 'update_type',
                      'image_url', 'video_url', 'is_important', 'is_published']
    
    for field in allowed_fields:
        if field in data:
            setattr(update, field, data[field])
    
    db.session.commit()
    
    return jsonify({
        'message': 'Mise à jour modifiée',
        'update': update.to_dict()
    }), 200


@harvest_bp.route('/<int:update_id>', methods=['DELETE'])
@login_required
def delete_update(update_id):
    """Supprime une mise à jour"""
    update = HarvestUpdate.query.get_or_404(update_id)
    
    if update.project.farmer_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Non autorisé'}), 403
    
    db.session.delete(update)
    db.session.commit()
    
    return jsonify({'message': 'Mise à jour supprimée'}), 200


@harvest_bp.route('/<int:update_id>/publish', methods=['POST'])
@login_required
def publish_update(update_id):
    """Publie une mise à jour"""
    update = HarvestUpdate.query.get_or_404(update_id)
    
    if update.project.farmer_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Non autorisé'}), 403
    
    update.is_published = True
    db.session.commit()
    
    return jsonify({'message': 'Mise à jour publiée'}), 200