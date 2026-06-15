"""
Routes pour les transferts internationaux
"""

from flask import request, jsonify, Blueprint
from flask_login import login_required, current_user
from app.api import api_bp
from app.models import FundTransfer, InternationalTransferPartner, Contribution, Project
from app.extensions import db
from app.utils.decorators import admin_required
import json


transfer_bp = Blueprint('transfers', __name__, url_prefix='/transfers')


@transfer_bp.route('/partners', methods=['GET'])
def get_transfer_partners():
    """Liste les partenaires de transfert disponibles"""
    partners = InternationalTransferPartner.query.filter_by(is_active=True).all()
    
    user_country = request.args.get('country', 'US')
    
    available = []
    for partner in partners:
        countries = json.loads(partner.countries_from) if partner.countries_from else []
        if user_country in countries:
            available.append(partner.to_dict())
    
    return jsonify({
        'partners': available
    }), 200


@transfer_bp.route('/batches', methods=['GET'])
@login_required
@admin_required
def list_transfer_batches():
    """Liste tous les lots de transfert"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
    
    query = FundTransfer.query
    
    if status:
        query = query.filter_by(status=status)
    
    pagination = query.order_by(FundTransfer.initiated_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'transfers': [t.to_dict() for t in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    }), 200


@transfer_bp.route('/batches', methods=['POST'])
@login_required
@admin_required
def create_transfer_batch():
    """Crée un lot de transfert pour les contributions collectées"""
    data = request.get_json()
    contribution_ids = data.get('contribution_ids', [])
    
    if not contribution_ids:
        return jsonify({'error': 'Aucune contribution sélectionnée'}), 400
    
    # Récupérer les contributions
    contributions = Contribution.query.filter(
        Contribution.id.in_(contribution_ids),
        Contribution.status == 'completed',
        Contribution.transfer_batch_id.is_(None)
    ).all()
    
    if not contributions:
        return jsonify({'error': 'Aucune contribution valide trouvée'}), 400
    
    # Calculer le total
    total_amount = sum(c.amount_htg for c in contributions)
    
    # Créer le lot
    batch_id = f'BATCH-{utc_now().strftime("%Y%m%d-%H%M%S")}'
    
    transfer = FundTransfer(
        batch_id=batch_id,
        source_country='INTL',
        source_gateway=data.get('source_gateway', 'wise'),
        destination_bank=data.get('destination_bank'),
        destination_account=data.get('destination_account'),
        beneficiary_name=data.get('beneficiary_name'),
        amount_source_currency=total_amount,
        source_currency='HTG',
        exchange_rate=1,  # À mettre à jour selon devise source
        amount_htg=total_amount,
        transfer_method=data.get('transfer_method', 'wise'),
        transfer_reference=batch_id,
        contribution_ids=json.dumps(contribution_ids)
    )
    
    db.session.add(transfer)
    
    # Marquer les contributions
    for contribution in contributions:
        contribution.transfer_batch_id = batch_id
    
    db.session.commit()
    
    # Déclencher le transfert via le partenaire
    # process_transfer(transfer)
    
    return jsonify({
        'message': 'Lot de transfert créé',
        'transfer': transfer.to_dict()
    }), 201


@transfer_bp.route('/batches/<int:transfer_id>', methods=['GET'])
@login_required
def get_transfer_batch(transfer_id):
    """Récupère un lot de transfert"""
    transfer = FundTransfer.query.get_or_404(transfer_id)
    
    # Vérifier les droits
    if not current_user.is_admin:
        return jsonify({'error': 'Non autorisé'}), 403
    
    # Récupérer les contributions associées
    contribution_ids = json.loads(transfer.contribution_ids) if transfer.contribution_ids else []
    contributions = Contribution.query.filter(Contribution.id.in_(contribution_ids)).all()
    
    return jsonify({
        'transfer': transfer.to_dict(),
        'contributions': [c.to_dict() for c in contributions]
    }), 200


@transfer_bp.route('/batches/<int:transfer_id>/status', methods=['PUT'])
@login_required
@admin_required
def update_transfer_status(transfer_id):
    """Met à jour le statut d'un transfert"""
    transfer = FundTransfer.query.get_or_404(transfer_id)
    
    data = request.get_json()
    new_status = data.get('status')
    external_id = data.get('external_transaction_id')
    
    if new_status:
        transfer.status = new_status
        
        if new_status == 'completed':
            transfer.completed_at = utc_now()
            # Marquer les contributions comme transférées
            contribution_ids = json.loads(transfer.contribution_ids) if transfer.contribution_ids else []
            for contribution in Contribution.query.filter(Contribution.id.in_(contribution_ids)).all():
                contribution.status = 'transferred'
    
    if external_id:
        transfer.external_transaction_id = external_id
    
    db.session.commit()
    
    return jsonify({
        'message': 'Statut mis à jour',
        'transfer': transfer.to_dict()
    }), 200


@transfer_bp.route('/summary', methods=['GET'])
@login_required
@admin_required
def get_transfer_summary():
    """Résumé des transferts"""
    # Total des fonds collectés
    total_collected = db.session.query(db.func.sum(Contribution.amount_htg)).filter_by(
        status='completed'
    ).scalar() or 0
    
    # Total transféré
    total_transferred = db.session.query(db.func.sum(FundTransfer.amount_htg)).filter_by(
        status='completed'
    ).scalar() or 0
    
    # En attente de transfert
    pending_transfer = total_collected - total_transferred
    
    return jsonify({
        'total_collected_htg': float(total_collected),
        'total_transferred_htg': float(total_transferred),
        'pending_transfer_htg': float(pending_transfer),
        'pending_batches': FundTransfer.query.filter_by(status='pending').count(),
        'processing_batches': FundTransfer.query.filter_by(status='processing').count(),
        'completed_batches': FundTransfer.query.filter_by(status='completed').count()
    }), 200