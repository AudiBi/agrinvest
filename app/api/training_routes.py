"""
Routes pour les formations agricoles
"""

from flask import request, jsonify, send_file, Blueprint
from flask_login import login_required, current_user
from app.api import api_bp
from app.models import Training, TrainingProgress, User
from app.extensions import db
from app.utils.decorators import farmer_required, admin_required
import os


training_bp = Blueprint('training', __name__, url_prefix='/trainings')


@training_bp.route('', methods=['GET'])
def list_trainings():
    """Liste toutes les formations disponibles"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 12, type=int)
    category = request.args.get('category')
    difficulty = request.args.get('difficulty')
    region = request.args.get('region')
    search = request.args.get('search')
    
    query = Training.query.filter_by(is_published=True)
    
    if category:
        query = query.filter_by(category=category)
    if difficulty:
        query = query.filter_by(difficulty_level=difficulty)
    if region:
        query = query.filter(
            (Training.region_specific == region) | 
            (Training.region_specific.is_(None))
        )
    if search:
        query = query.filter(
            Training.title_ht.ilike(f'%{search}%') |
            Training.title_fr.ilike(f'%{search}%') |
            Training.description_ht.ilike(f'%{search}%')
        )
    
    pagination = query.order_by(Training.sort_order, Training.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    language = request.args.get('lang', 'ht')
    
    return jsonify({
        'trainings': [t.to_dict(language=language) for t in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages,
        'categories': [
            {'name': c[0], 'count': c[1]} 
            for c in db.session.query(
                Training.category, 
                db.func.count(Training.id)
            ).filter_by(is_published=True).group_by(Training.category).all()
        ]
    }), 200


@training_bp.route('/featured', methods=['GET'])
def get_featured_trainings():
    """Récupère les formations à la une"""
    limit = request.args.get('limit', 6, type=int)
    language = request.args.get('lang', 'ht')
    
    trainings = Training.query.filter_by(
        is_published=True,
        is_featured=True
    ).order_by(
        Training.sort_order
    ).limit(limit).all()
    
    return jsonify({
        'trainings': [t.to_dict(language=language) for t in trainings]
    }), 200


@training_bp.route('/<int:training_id>', methods=['GET'])
def get_training(training_id):
    """Récupère une formation spécifique"""
    training = Training.query.get_or_404(training_id)
    language = request.args.get('lang', 'ht')
    
    return jsonify(training.to_dict(language=language)), 200


@training_bp.route('/<int:training_id>/progress', methods=['POST'])
@login_required
@farmer_required
def update_progress(training_id):
    """Met à jour la progression d'une formation"""
    training = Training.query.get_or_404(training_id)
    
    data = request.get_json()
    progress = TrainingProgress.query.filter_by(
        farmer_id=current_user.id,
        training_id=training_id
    ).first()
    
    if not progress:
        progress = TrainingProgress(
            farmer_id=current_user.id,
            training_id=training_id
        )
        db.session.add(progress)
    
    if 'progress_percentage' in data:
        progress.progress_percentage = data['progress_percentage']
    
    if 'last_position_seconds' in data:
        progress.update_progress(data['last_position_seconds'])
    
    if data.get('completed', False):
        progress.mark_completed()
    
    db.session.commit()
    
    return jsonify({
        'message': 'Progression mise à jour',
        'progress': progress.to_dict()
    }), 200


@training_bp.route('/my-progress', methods=['GET'])
@login_required
def get_my_progress():
    """Récupère la progression de l'utilisateur"""
    if not current_user.is_farmer:
        return jsonify({'error': 'Réservé aux agriculteurs'}), 403
    
    progress = TrainingProgress.query.filter_by(
        farmer_id=current_user.id
    ).all()
    
    # Statistiques
    completed = [p for p in progress if p.status == 'completed']
    in_progress = [p for p in progress if p.status == 'started']
    
    return jsonify({
        'progress': [p.to_dict() for p in progress],
        'stats': {
            'total_started': len(progress),
            'completed': len(completed),
            'in_progress': len(in_progress),
            'completion_rate': round(len(completed) / len(progress) * 100) if progress else 0
        }
    }), 200


@training_bp.route('/certificate/<int:training_id>', methods=['GET'])
@login_required
@farmer_required
def get_certificate(training_id):
    """Génère un certificat de complétion"""
    progress = TrainingProgress.query.filter_by(
        farmer_id=current_user.id,
        training_id=training_id,
        status='completed'
    ).first_or_404()
    
    if not progress.certificate_generated:
        # Générer le certificat (à implémenter)
        # certificate_url = generate_certificate(progress)
        # progress.certificate_url = certificate_url
        # progress.certificate_generated = True
        # db.session.commit()
        pass
    
    # Retourner le certificat
    return jsonify({
        'certificate_url': progress.certificate_url
    }), 200


@training_bp.route('', methods=['POST'])
@login_required
@admin_required
def create_training():
    """Crée une nouvelle formation (admin seulement)"""
    data = request.get_json()
    
    training = Training(
        title_ht=data['title_ht'],
        title_fr=data.get('title_fr'),
        title_en=data.get('title_en'),
        description_ht=data['description_ht'],
        description_fr=data.get('description_fr'),
        description_en=data.get('description_en'),
        content_type=data['content_type'],
        content_url=data['content_url'],
        thumbnail_url=data.get('thumbnail_url'),
        file_size_mb=data.get('file_size_mb'),
        duration_minutes=data.get('duration_minutes'),
        content_url_light=data.get('content_url_light'),
        audio_only_url=data.get('audio_only_url'),
        is_downloadable=data.get('is_downloadable', True),
        whatsapp_forwardable=data.get('whatsapp_forwardable', True),
        category=data['category'],
        difficulty_level=data.get('difficulty_level', 'beginner'),
        region_specific=data.get('region_specific'),
        is_featured=data.get('is_featured', False),
        created_by_id=current_user.id
    )
    
    db.session.add(training)
    db.session.commit()
    
    return jsonify({
        'message': 'Formation créée',
        'training': training.to_dict()
    }), 201