"""
Routes pour les commissions plateforme et CEO
"""

from app.models.user import utc_now
from flask import request, jsonify, Blueprint
from flask_login import login_required, current_user
from app.api import api_bp
from app.models import (
    PlatformCommissionConfig, PlatformEarning, CEOPayout, 
    CommissionAuditLog, Project, User
)
from app.extensions import db
from app.utils.decorators import admin_required
from decimal import Decimal, InvalidOperation
import json
import uuid


commission_bp = Blueprint('commission', __name__, url_prefix='/commission')


def _parse_money(value):
    """Montant décimal fini et positif ou nul (ValueError sinon)."""
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        raise ValueError(f'Montant invalide : {value!r}')
    if not amount.is_finite() or amount < 0:
        raise ValueError(f'Montant invalide : {value!r}')
    return amount


def _parse_percentage(value):
    """Pourcentage entre 0 et 20 (borne imposée par la base de données)."""
    amount = _parse_money(value)
    if amount > 20:
        raise ValueError('Le pourcentage doit être compris entre 0 et 20')
    return amount


@commission_bp.route('/config', methods=['GET'])
@login_required
@admin_required
def get_commission_configs():
    """Récupère toutes les configurations de commission"""
    configs = PlatformCommissionConfig.query.filter_by(is_active=True).all()
    default = PlatformCommissionConfig.query.filter_by(is_default=True, is_active=True).first()

    return jsonify({
        'configs': [c.to_dict() for c in configs],
        'default_commission': float(default.percentage) if default else 3.0
    }), 200


@commission_bp.route('/config', methods=['POST'])
@login_required
@admin_required
def create_commission_config():
    """Crée une nouvelle configuration de commission"""
    data = request.get_json(silent=True) or {}

    try:
        if not data.get('commission_type'):
            raise ValueError('commission_type requis')
        percentage = _parse_percentage(data.get('percentage'))
        min_amount = _parse_money(data.get('min_amount', 0))
        max_amount = _parse_money(data['max_amount']) if data.get('max_amount') else None
        fixed_fee = _parse_money(data.get('fixed_fee', 0))
        min_amount_to_apply = _parse_money(data.get('min_amount_to_apply', 0))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    config = PlatformCommissionConfig(
        commission_type=data['commission_type'],
        percentage=percentage,
        project_category=data.get('project_category'),
        applies_on=data.get('applies_on', 'amount_raised'),
        min_amount=min_amount,
        max_amount=max_amount,
        fixed_fee=fixed_fee,
        min_amount_to_apply=min_amount_to_apply,
        description_fr=data.get('description_fr'),
        description_ht=data.get('description_ht'),
        is_default=bool(data.get('is_default', False)),
        created_by_id=current_user.id
    )
    
    # Si c'est la configuration par défaut, désactiver les autres
    if config.is_default:
        PlatformCommissionConfig.query.update({PlatformCommissionConfig.is_default: False})
    
    db.session.add(config)
    db.session.flush()  # id de la config, sans valider : configuration et journal dans la même transaction

    db.session.add(CommissionAuditLog(
        action='create',
        config_id=config.id,
        new_percentage=config.percentage,
        changed_by_id=current_user.id,
        reason=data.get('reason')
    ))
    db.session.commit()
    
    return jsonify({
        'message': 'Configuration créée',
        'config': config.to_dict()
    }), 201


@commission_bp.route('/config/<int:config_id>', methods=['PUT'])
@login_required
@admin_required
def update_commission_config(config_id):
    """Met à jour une configuration de commission"""
    config = PlatformCommissionConfig.query.get_or_404(config_id)
    
    data = request.get_json(silent=True) or {}
    old_percentage = config.percentage

    if 'percentage' in data:
        try:
            config.percentage = _parse_percentage(data['percentage'])
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
    if 'is_active' in data:
        config.is_active = bool(data['is_active'])
    if 'is_default' in data and data['is_default']:
        PlatformCommissionConfig.query.update({PlatformCommissionConfig.is_default: False})
        config.is_default = True
    if 'description_fr' in data:
        config.description_fr = data['description_fr']

    db.session.add(CommissionAuditLog(
        action='update',
        config_id=config.id,
        old_percentage=old_percentage,
        new_percentage=config.percentage,
        changed_by_id=current_user.id,
        reason=data.get('reason')
    ))
    db.session.commit()  # configuration et journal validés ensemble
    
    return jsonify({
        'message': 'Configuration mise à jour',
        'config': config.to_dict()
    }), 200


@commission_bp.route('/earnings', methods=['GET'])
@login_required
@admin_required
def get_earnings():
    """Récupère tous les gains de la plateforme"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    status = request.args.get('status')
    project_id = request.args.get('project_id', type=int)
    
    query = PlatformEarning.query

    if status:
        query = query.filter_by(status=status)
    if project_id:
        query = query.filter_by(project_id=project_id)
    
    pagination = query.order_by(PlatformEarning.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'earnings': [e.to_dict() for e in pagination.items],
        'total': pagination.total,
        'total_amount': float(db.session.query(db.func.sum(PlatformEarning.commission_amount_htg)).filter(
            PlatformEarning.status != 'cancelled').scalar() or 0),
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    }), 200


@commission_bp.route('/earnings/summary', methods=['GET'])
@login_required
@admin_required
def get_earnings_summary():
    """Résumé des gains par période"""
    period = request.args.get('period', 'month')  # day, week, month, year
    
    from app.utils.date_utils import get_date_range
    
    start_date, end_date = get_date_range(period)
    
    # Même périmètre pour le total et le détail : commissions générées, hors annulées (remboursements)
    by_project = db.session.query(
        PlatformEarning.project_id,
        db.func.sum(PlatformEarning.commission_amount_htg).label('total')
    ).filter(
        PlatformEarning.created_at.between(start_date, end_date),
        PlatformEarning.status != 'cancelled'
    ).group_by(PlatformEarning.project_id).all()

    total = sum(p[1] for p in by_project)
    
    return jsonify({
        'period': period,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'total_earnings_htg': float(total),
        'projects_count': len(by_project),
        'by_project': [
            {
                'project_id': p[0],
                'project_title': Project.query.get(p[0]).title if Project.query.get(p[0]) else None,
                'total': float(p[1])
            } for p in by_project
        ]
    }), 200


@commission_bp.route('/payouts', methods=['GET'])
@login_required
@admin_required
def get_payouts():
    """Récupère tous les paiements au CEO"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    pagination = CEOPayout.query.order_by(CEOPayout.initiated_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'payouts': [p.to_dict() for p in pagination.items],
        'total': pagination.total,
        'total_paid': float(db.session.query(db.func.sum(CEOPayout.payout_amount)).filter_by(
            status='completed'
        ).scalar() or 0),
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    }), 200


@commission_bp.route('/payouts', methods=['POST'])
@login_required
@admin_required
def create_payout():
    """Crée un paiement pour le CEO"""
    data = request.get_json(silent=True) or {}

    try:
        transfer_fee = _parse_money(data.get('transfer_fee', 0))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    # Verrou des lignes (PostgreSQL) : deux demandes simultanées ne peuvent pas verser deux fois
    unpaid_earnings = PlatformEarning.query.filter_by(
        paid_to_ceo=False,
        status='pending'
    ).with_for_update().all()

    if not unpaid_earnings:
        return jsonify({'error': 'Aucune commission à payer'}), 400

    total_amount = sum(e.commission_amount_htg for e in unpaid_earnings)
    if transfer_fee > total_amount:
        return jsonify({'error': 'Les frais de transfert dépassent le montant à verser'}), 400

    payout = CEOPayout(
        payout_reference=f'CEO-{utc_now().strftime("%Y%m%d-%H%M%S")}-{uuid.uuid4().hex[:6]}',
        period_start=unpaid_earnings[0].created_at,
        period_end=utc_now(),
        total_earnings=total_amount,
        total_earnings_htg=total_amount,
        earnings_ids=json.dumps([e.id for e in unpaid_earnings]),
        projects_breakdown=json.dumps(list(set(e.project_id for e in unpaid_earnings))),
        payout_method=data.get('payout_method', 'bank_transfer'),
        payout_account=data.get('payout_account'),
        payout_amount=total_amount,
        payout_currency='HTG',
        net_received=total_amount - transfer_fee,
        created_by_id=current_user.id
    )
    
    db.session.add(payout)
    
    # Marquer les earnings comme en attente de paiement
    for earning in unpaid_earnings:
        earning.status = 'pending_payout'
        earning.payout_reference = payout.payout_reference
    
    db.session.commit()
    
    return jsonify({
        'message': 'Paiement créé',
        'payout': payout.to_dict()
    }), 201


@commission_bp.route('/payouts/<int:payout_id>/complete', methods=['POST'])
@login_required
@admin_required
def complete_payout(payout_id):
    """Marque un paiement comme complété"""
    payout = CEOPayout.query.get_or_404(payout_id)

    if payout.status == 'completed':
        return jsonify({'message': 'Paiement déjà complété', 'payout': payout.to_dict()}), 200
    if payout.status not in ('pending', 'processing'):
        return jsonify({'error': f'Un paiement « {payout.status} » ne peut pas être complété'}), 409

    payout.status = 'completed'
    payout.completed_at = utc_now()
    
    # Marquer les earnings comme payés
    earnings_ids = json.loads(payout.earnings_ids) if payout.earnings_ids else []
    PlatformEarning.query.filter(PlatformEarning.id.in_(earnings_ids)).update({
        'paid_to_ceo': True,
        'paid_at': utc_now(),
        'status': 'paid'
    })
    
    db.session.commit()
    
    return jsonify({
        'message': 'Paiement marqué comme complété',
        'payout': payout.to_dict()
    }), 200


@commission_bp.route('/dashboard', methods=['GET'])
@login_required
@admin_required
def get_commission_dashboard():
    """Tableau de bord des commissions pour le CEO"""
    
    default = PlatformCommissionConfig.query.filter_by(is_default=True, is_active=True).first()

    # Total des commissions générées
    total_commissions = db.session.query(
        db.func.sum(PlatformEarning.commission_amount_htg)
    ).filter(PlatformEarning.status != 'cancelled').scalar() or 0
    
    # Commissions payées au CEO
    paid_to_ceo = db.session.query(
        db.func.sum(CEOPayout.payout_amount)
    ).filter(CEOPayout.status == 'completed').scalar() or 0
    
    # Commissions en attente
    pending_commissions = total_commissions - paid_to_ceo
    
    # Par mois
    from app.utils.date_utils import get_last_months
    
    monthly = []
    for month in get_last_months(6):
        start, end = month['start'], month['end']
        monthly_total = db.session.query(
            db.func.sum(PlatformEarning.commission_amount_htg)
        ).filter(
            PlatformEarning.created_at.between(start, end)
        ).scalar() or 0
        
        monthly.append({
            'month': month['name'],
            'amount': float(monthly_total)
        })
    
    return jsonify({
        'total_commissions_htg': float(total_commissions),
        'paid_to_ceo_htg': float(paid_to_ceo),
        'pending_commissions_htg': float(pending_commissions),
        'monthly_breakdown': monthly,
        'current_commission_rate': float(default.percentage) if default else 3.0
    }), 200