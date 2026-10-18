"""
Routes pour les points de collecte (cash en Haïti)
"""

from app.utils.audit import record_audit
from decimal import Decimal, InvalidOperation
from flask import request, jsonify, Blueprint, current_app
from flask_login import login_required, current_user
from app.api import api_bp
from app.models import CollectionPoint, ProjectCollectionPoint, Project, Contribution
from app.extensions import db
from app.utils.decorators import admin_required, agent_required


collection_bp = Blueprint('collections', __name__, url_prefix='/collection-points')


def _parse_fee(value):
    """Frais de collecte en % : décimal fini entre 0 et 100."""
    try:
        fee = Decimal(str(value))
    except InvalidOperation:
        raise ValueError('fee_percentage invalide')
    if not fee.is_finite() or fee < 0 or fee > 100:
        raise ValueError('fee_percentage doit être compris entre 0 et 100')
    return fee


def _check_coordinates(latitude, longitude):
    for value, limit, name in ((latitude, 90, 'latitude'), (longitude, 180, 'longitude')):
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                  or not -limit <= value <= limit):
            raise ValueError(f'{name} invalide')


def _existing_project_ids(project_ids):
    if not isinstance(project_ids, list) or not all(
            isinstance(i, int) and not isinstance(i, bool) for i in project_ids):
        raise ValueError('project_ids : liste d\'identifiants requise')
    found = {p.id for p in Project.query.filter(Project.id.in_(project_ids)).all()} if project_ids else set()
    unknown = sorted(set(project_ids) - found)
    if unknown:
        raise ValueError(f'Projets introuvables : {unknown}')
    return sorted(set(project_ids))


@collection_bp.route('/<int:point_id>/receive-cash', methods=['POST'])
@login_required
@agent_required
def receive_cash(point_id):
    """Un agent confirme avoir reçu les espèces d'une contribution au point de collecte.

    La contribution (méthode « cash ») est confirmée seulement si le montant remis est exactement
    celui promis, si le projet est rattaché à ce point et si le numéro de reçu est neuf.
    """
    point = CollectionPoint.query.get_or_404(point_id)
    data = request.get_json(silent=True) or {}

    if not point.is_active:
        return jsonify({'error': 'Ce point de collecte est inactif'}), 409

    receipt = str(data.get('receipt_number') or '').strip()
    if not receipt or len(receipt) > 50:
        return jsonify({'error': 'receipt_number requis (50 caractères max)'}), 400
    if Contribution.query.filter_by(cash_receipt_number=receipt).first():
        return jsonify({'error': 'Ce numéro de reçu a déjà été utilisé'}), 409

    try:
        amount = Decimal(str(data.get('amount')))
        contribution_id = int(data.get('contribution_id'))
    except (InvalidOperation, TypeError, ValueError):
        return jsonify({'error': 'contribution_id et amount requis'}), 400

    contribution = Contribution.query.filter_by(id=contribution_id).with_for_update().first()
    if not contribution or contribution.payment_method != 'cash':
        return jsonify({'error': 'Contribution en espèces introuvable'}), 404
    if contribution.status != 'pending':
        return jsonify({'error': f'Contribution déjà « {contribution.status} »'}), 409

    linked = ProjectCollectionPoint.query.filter_by(
        project_id=contribution.project_id, collection_point_id=point.id, is_active=True).first()
    if not linked:
        return jsonify({'error': "Ce projet n'est pas rattaché à ce point de collecte"}), 400

    if amount != contribution.amount_htg:
        return jsonify({'error': f'Montant remis différent du montant promis ({contribution.amount_htg} HTG)'}), 400

    contribution.collection_point_id = point.id
    contribution.cash_receipt_number = receipt
    contribution.gateway_fee = (amount * (point.fee_percentage or 0) / 100).quantize(Decimal('0.01'))
    record_audit('cash.receive', contribution, point_id=point.id, receipt=receipt, amount_htg=amount,
                 fee=contribution.gateway_fee)
    contribution.mark_completed()

    current_app.logger.info(
        f"Espèces reçues : contribution {contribution.id}, point {point.id}, reçu {receipt}, agent {current_user.id}")
    return jsonify({'message': 'Espèces enregistrées', 'contribution': contribution.to_dict()}), 200


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
    data = request.get_json(silent=True) or {}

    missing = [f for f in ('name', 'department', 'commune', 'address') if not data.get(f)]
    if missing:
        return jsonify({'error': f'Champs requis : {", ".join(missing)}'}), 400
    try:
        fee = _parse_fee(data.get('fee_percentage', 0))
        _check_coordinates(data.get('latitude'), data.get('longitude'))
        project_ids = _existing_project_ids(data.get('project_ids') or [])
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

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
        fee_percentage=fee
    )

    db.session.add(point)
    db.session.flush()
    record_audit('collection_point.create', point, fee_percentage=fee)
    # Lier aux projets si spécifiés (point et liens validés ensemble)
    for project_id in project_ids:
        db.session.add(ProjectCollectionPoint(project_id=project_id, collection_point_id=point.id))
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
    
    data = request.get_json(silent=True) or {}

    allowed_fields = ['name', 'department', 'commune', 'address', 'latitude', 'longitude',
                      'manager_name', 'manager_phone', 'opening_hours', 'fee_percentage', 'is_active']

    try:
        if 'fee_percentage' in data:
            data['fee_percentage'] = _parse_fee(data['fee_percentage'])
        _check_coordinates(data.get('latitude', point.latitude), data.get('longitude', point.longitude))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    changes = {f: [str(getattr(point, f)), str(data[f])] for f in allowed_fields
               if f in data and str(getattr(point, f)) != str(data[f])}
    if changes:
        record_audit('collection_point.update', point, changes=changes)
    for field in allowed_fields:
        if field in data:
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
    data = request.get_json(silent=True) or {}
    try:
        project_ids = _existing_project_ids(data.get('project_ids', []))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

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
    
    if lat is None or lng is None or not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return jsonify({'error': 'Coordonnées valides requises'}), 400
    
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
        if point.latitude is not None and point.longitude is not None:
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