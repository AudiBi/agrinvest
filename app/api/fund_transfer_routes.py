"""
Routes pour les transferts internationaux
"""

from app.models.user import utc_now
from flask import request, jsonify, Blueprint
from flask_login import login_required, current_user
from app.api import api_bp
from app.models import FundTransfer, InternationalTransferPartner, Contribution, Project
from app.extensions import db
from app.utils.decorators import admin_required
import uuid
import json


transfer_bp = Blueprint('transfers', __name__, url_prefix='/transfers')

# Transitions autorisées d'un lot ; completed / failed / cancelled sont terminaux
TRANSFER_TRANSITIONS = {
    'pending': ('processing', 'completed', 'failed', 'cancelled'),
    'processing': ('completed', 'failed', 'cancelled'),
    'completed': (),
    'failed': (),
    'cancelled': (),
}


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
    data = request.get_json(silent=True) or {}
    contribution_ids = data.get('contribution_ids', [])

    if (not isinstance(contribution_ids, list) or not contribution_ids
            or not all(isinstance(i, int) and not isinstance(i, bool) for i in contribution_ids)):
        return jsonify({'error': 'contribution_ids : liste d\'identifiants requise'}), 400

    missing = [f for f in ('destination_bank', 'destination_account', 'beneficiary_name') if not data.get(f)]
    if missing:
        return jsonify({'error': f'Champs requis : {", ".join(missing)}'}), 400

    # Récupérer les contributions (verrou PostgreSQL : un lot concurrent ne peut pas les reprendre)
    contributions = Contribution.query.filter(
        Contribution.id.in_(contribution_ids),
        Contribution.status == 'completed',
        Contribution.transfer_batch_id.is_(None)
    ).with_for_update().all()

    if not contributions:
        return jsonify({'error': 'Aucune contribution valide trouvée'}), 400

    included_ids = [c.id for c in contributions]
    skipped_ids = sorted(set(contribution_ids) - set(included_ids))

    # Calculer le total
    total_amount = sum(c.amount_htg for c in contributions)

    # Créer le lot
    batch_id = f'BATCH-{utc_now().strftime("%Y%m%d-%H%M%S")}-{uuid.uuid4().hex[:6]}'
    
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
        contribution_ids=json.dumps(included_ids)  # uniquement les contributions réellement incluses
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
        'transfer': transfer.to_dict(),
        'skipped_contribution_ids': skipped_ids
    }), 201


@transfer_bp.route('/batches/<int:transfer_id>', methods=['GET'])
@login_required
@admin_required  # avant la recherche : un non-admin ne peut pas deviner quels lots existent (404 vs 403)
def get_transfer_batch(transfer_id):
    """Récupère un lot de transfert"""
    transfer = FundTransfer.query.get_or_404(transfer_id)
    
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
    
    data = request.get_json(silent=True) or {}
    new_status = data.get('status')
    external_id = data.get('external_transaction_id')

    if new_status and new_status != transfer.status:
        if new_status not in TRANSFER_TRANSITIONS.get(transfer.status, ()):
            return jsonify({'error': f'Transition « {transfer.status} » -> « {new_status} » interdite'}), 409
        transfer.status = new_status

        if new_status == 'completed':
            transfer.completed_at = utc_now()
            # Le statut des contributions reste « completed » : elles sont transférées via le lot
        elif new_status in ('failed', 'cancelled'):
            # Les contributions redeviennent disponibles pour un nouveau lot
            contribution_ids = json.loads(transfer.contribution_ids) if transfer.contribution_ids else []
            Contribution.query.filter(
                Contribution.id.in_(contribution_ids),
                Contribution.transfer_batch_id == transfer.batch_id
            ).update({'transfer_batch_id': None}, synchronize_session=False)
    elif new_status and new_status not in TRANSFER_TRANSITIONS:
        return jsonify({'error': f'Statut inconnu : {new_status}'}), 400

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