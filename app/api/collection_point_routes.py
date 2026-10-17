"""
Routes pour les points de collecte (cash en Haïti)
"""

from decimal import Decimal
from flask import request, jsonify, Blueprint
from flask_login import login_required, current_user
from app.api import api_bp
from app.models import CollectionPoint, ProjectCollectionPoint
from app.extensions import db
from app.utils.decorators import admin_required, agent_required


collection_bp = Blueprint('collections', __name__, url_prefix='/collection-points')


@collection_bp.route('', methods=['GET'])
def list_collection_points():
    """Liste tous les points de collecte"""
    department = request.args.get('department')
    commune = request.args.get('commune')
    project_id = request.args.get('project_id', type=int)
    
    query = CollectionPoint.query.filter_by(is_active=True)
    
    if department:
        query = query.filter_by(department=department)
    if commune:
        query = query.filter_by(commune=commune)
    
    points = query.all()
    
    # Si un projet est spécifié, ajouter l'information si le point accepte ce projet
    result = []
    for point in points:
        point_dict = point.to_dict()
        if project_id:
            link = ProjectCollectionPoint.query.filter_by(
                project_id=project_id,
                collection_point_id=point.id,
                is_active=True
            ).first()
            point_dict['accepts_project'] = link is not None
        result.append(point_dict)
    
    return jsonify({
        'collection_points': result
    }), 200


@collection_bp.route('', methods=['POST'])
@login_required
@admin_required
def create_collection_point():
    """Crée un point de collecte (admin seulement)"""
    data = request.get_json()
    
    point = CollectionPoint(
        name=data['name'],
        department=data['department'],
        commune=data['commune'],
        address=data['address'],
        latitude=data.get('latitude'),
        longitude=data.get('longitude'),
        manager_name=data.get('manager_name'),
        manager_phone=data.get('manager_phone'),
        opening_hours=data.get('opening_hours'),
        fee_percentage=Decimal(str(data.get('fee_percentage', 0)))
    )
    
    db.session.add(point)
    db.session.commit()
    
    # Lier aux projets si spécifiés
    if data.get('project_ids'):
        for project_id in data['project_ids']:
            link = ProjectCollectionPoint(
                project_id=project_id,
                collection_point_id=point.id
            )
            db.session.add(link)
        db.session.commit()
    
    return jsonify({
        'message': 'Point de collecte créé',
        'collection_point': point.to_dict()
    }), 201


@collection_bp.route('/<int:point_id>', methods=['PUT'])
@login_required
@admin_required
def update_collection_point(point_id):
    """Met à jour un point de collecte"""
    point = CollectionPoint.query.get_or_404(point_id)
    
    data = request.get_json()
    
    allowed_fields = ['name', 'department', 'commune', 'address', 'latitude', 'longitude',
                      'manager_name', 'manager_phone', 'opening_hours', 'fee_percentage', 'is_active']
    
    for field in allowed_fields:
        if field in data:
            if field == 'fee_percentage':
                setattr(point, field, Decimal(str(data[field])))
            else:
                setattr(point, field, data[field])
    
    db.session.commit()
    
    return jsonify({
        'message': 'Point de collecte mis à jour',
        'collection_point': point.to_dict()
    }), 200


@collection_bp.route('/<int:point_id>/projects', methods=['POST'])
@login_required
@admin_required
def link_projects_to_point(point_id):
    """Lie des projets à un point de collecte"""
    point = CollectionPoint.query.get_or_404(point_id)
    data = request.get_json()
    project_ids = data.get('project_ids', [])
    
    for project_id in project_ids:
        existing = ProjectCollectionPoint.query.filter_by(
            project_id=project_id,
            collection_point_id=point_id
        ).first()
        
        if not existing:
            link = ProjectCollectionPoint(
                project_id=project_id,
                collection_point_id=point_id
            )
            db.session.add(link)
    
    db.session.commit()
    
    return jsonify({'message': f'{len(project_ids)} projet(s) lié(s)'}), 200


@collection_bp.route('/nearby', methods=['GET'])
def get_nearby_points():
    """Trouve les points de collecte proches"""
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    radius = request.args.get('radius', 10, type=float)  # km
    
    if not lat or not lng:
        return jsonify({'error': 'Coordonnées requises'}), 400
    
    # Calcul de distance approximatif
    # À améliorer avec PostGIS en production
    points = CollectionPoint.query.filter_by(is_active=True).all()
    
    from math import radians, sin, cos, sqrt, atan2
    
    def distance(lat1, lon1, lat2, lon2):
        R = 6371  # Rayon Terre en km
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return R * c
    
    nearby = []
    for point in points:
        if point.latitude and point.longitude:
            dist = distance(lat, lng, point.latitude, point.longitude)
            if dist <= radius:
                point_dict = point.to_dict()
                point_dict['distance_km'] = round(dist, 2)
                nearby.append(point_dict)
    
    nearby.sort(key=lambda x: x['distance_km'])
    
    return jsonify({
        'points': nearby,
        'count': len(nearby)
    }), 200