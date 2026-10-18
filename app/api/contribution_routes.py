"""
Routes pour les contributions (investissements)
"""

from app.utils.audit import record_audit
from app.utils.pagination import per_page_arg
from decimal import Decimal, InvalidOperation

from flask import request, jsonify, current_app, url_for, Blueprint
from flask_login import login_required, current_user
from app.api import api_bp
from app.models import Contribution, Project, User, PaymentGatewayConfig
from app.extensions import db
from app.models.contribution import utc_now
from app.utils.decorators import rate_limit
from app.utils.payments import process_stripe_payment, process_paypal_payment, process_moncash_payment
import stripe


contribution_bp = Blueprint('contributions', __name__, url_prefix='/contributions')


@contribution_bp.route('/projects/<int:project_id>/invest', methods=['POST'])
@login_required
@rate_limit(limit=10, per=3600)
def create_contribution(project_id):
    """
    Crée une nouvelle contribution
    ---
    parameters:
      - name: project_id
        in: path
        required: true
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            amount: {type: number}
            currency: {type: string}
            payment_method: {type: string}
            is_anonymous: {type: boolean}
            message: {type: string}
    """
    project = Project.query.get_or_404(project_id)
    
    # Vérifier si le projet accepte les contributions
    data = request.get_json(silent=True) or {}
    
    try:
        amount = Decimal(str(data.get('amount')))
        if not amount.is_finite() or amount <= 0:
            raise InvalidOperation
    except InvalidOperation:
        return jsonify({'error': 'Montant requis et strictement positif'}), 400
    
    if data.get('payment_method') not in ('stripe', 'paypal', 'moncash'):
        return jsonify({'error': 'Méthode de paiement invalide'}), 400
    
    # Récupérer le taux de change
    from app.utils.exchange_rates import get_exchange_rate
    
    currency = (data.get('currency') or current_user.preferred_currency).upper()
    if data['payment_method'] in ('stripe', 'paypal') and currency == 'HTG':
        return jsonify({'error': "Ce moyen de paiement n'accepte pas le HTG : choisissez USD, EUR ou CAD"}), 400
    try:
        exchange_rate = get_exchange_rate(currency, 'HTG')
        project_rate = get_exchange_rate(currency, project.currency)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503
    amount_htg = amount * exchange_rate
    
    # Les bornes du projet sont exprimées dans sa propre devise
    can_accept, error = project.can_accept_contribution(amount * project_rate)
    if not can_accept:
        return jsonify({'error': error}), 400
    
    # Créer la contribution
    contribution = Contribution(
        investor_id=current_user.id,
        project_id=project_id,
        amount=amount,
        currency=currency,
        amount_htg=amount_htg,
        exchange_rate=exchange_rate,
        exchange_rate_date=utc_now(),
        payment_method=data['payment_method'],
        investor_country=current_user.country or 'HT',
        is_anonymous=data.get('is_anonymous', False),
        message=data.get('message')
    )
    
    db.session.add(contribution)
    db.session.commit()
    
    # Traiter le paiement selon la méthode
    payment_method = data['payment_method']
    payment_intent = None
    
    try:
        if payment_method == 'stripe':
            payment_intent = process_stripe_payment(contribution)
        elif payment_method == 'paypal':
            payment_intent = process_paypal_payment(contribution)
        elif payment_method == 'moncash':
            payment_intent = process_moncash_payment(contribution)
        
        # Mettre à jour l'ID de paiement
        if payment_intent:
            if payment_method == 'stripe':
                contribution.stripe_payment_intent_id = payment_intent['id']
            elif payment_method == 'paypal':
                contribution.paypal_order_id = payment_intent['id']
            elif payment_method == 'moncash':
                contribution.moncash_payment_id = payment_intent['payment_id']
            db.session.commit()
        
        return jsonify({
            'message': 'Contribution créée avec succès',
            'contribution': contribution.to_dict(),
            'payment_intent': payment_intent,
            'payment_url': payment_intent.get('approval_url') if payment_intent else None
        }), 201
        
    except Exception as e:
        contribution.status = 'failed'
        db.session.commit()
        return jsonify({'error': str(e)}), 400


@contribution_bp.route('/<int:contribution_id>/confirm', methods=['POST'])
@login_required
def confirm_contribution(contribution_id):
    """Confirme une contribution après paiement"""
    contribution = Contribution.query.get_or_404(contribution_id)
    
    if contribution.investor_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Non autorisé'}), 403
    
    if contribution.status != 'pending':
        return jsonify({'error': 'Cette contribution ne peut pas être confirmée'}), 400
    
    data = request.get_json()
    payment_intent_id = data.get('payment_intent_id')
    
    # Vérifier le paiement auprès du gateway
    from app.utils.payments import verify_payment
    
    is_valid = verify_payment(contribution, payment_intent_id)
    
    if not is_valid:
        contribution.mark_failed()
        return jsonify({'error': 'Paiement non validé'}), 400
    
    contribution.mark_completed()
    
    return jsonify({
        'message': 'Contribution confirmée avec succès',
        'contribution': contribution.to_dict()
    }), 200


@contribution_bp.route('/<int:contribution_id>', methods=['GET'])
@login_required
def get_contribution(contribution_id):
    """Récupère une contribution spécifique"""
    contribution = Contribution.query.get_or_404(contribution_id)
    
    if contribution.investor_id != current_user.id and \
       contribution.project.farmer_id != current_user.id and \
       not current_user.is_admin:
        return jsonify({'error': 'Non autorisé'}), 403
    
    return jsonify(contribution.to_dict()), 200


@contribution_bp.route('/<int:contribution_id>/refund', methods=['POST'])
@login_required
def refund_contribution(contribution_id):
    """Rembourse une contribution"""
    contribution = Contribution.query.get_or_404(contribution_id)
    
    # Seul l'admin ou le farmer peuvent rembourser
    if contribution.project.farmer_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Non autorisé'}), 403
    
    if contribution.status != 'completed':
        return jsonify({'error': 'Seules les contributions complétées peuvent être remboursées'}), 400

    if contribution.transfer_batch_id:
        return jsonify({'error': 'Contribution incluse dans un lot de transfert : remboursement impossible'}), 409
    
    # Traiter le remboursement via le gateway
    from app.utils.payments import process_refund
    
    try:
        refund_result = process_refund(contribution)
        
        if refund_result:
            record_audit('contribution.refund', contribution, amount_htg=contribution.amount_htg,
                         payment_method=contribution.payment_method)
            contribution.mark_refunded()
            return jsonify({'message': 'Contribution remboursée avec succès'}), 200
        else:
            return jsonify({'error': 'Erreur lors du remboursement'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@contribution_bp.route('/my-contributions', methods=['GET'])
@login_required
def get_my_contributions():
    """Récupère mes contributions"""
    page = request.args.get('page', 1, type=int)
    per_page = per_page_arg(20)
    status = request.args.get('status')
    
    query = Contribution.query.filter_by(investor_id=current_user.id)
    
    if status:
        query = query.filter_by(status=status)
    
    pagination = query.order_by(Contribution.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'contributions': [c.to_dict() for c in pagination.items],
        'total': pagination.total,
        'total_invested': float(current_user.get_total_invested()),
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    }), 200


@contribution_bp.route('/payment-methods', methods=['GET'])
def get_payment_methods():
    """Récupère les méthodes de paiement disponibles par pays"""
    user_country = request.args.get('country', 'HT')
    amount = request.args.get('amount', type=float)
    
    gateways = PaymentGatewayConfig.query.filter_by(
        country_code=user_country,
        is_active=True
    ).all()
    
    payment_methods = []
    for gateway in gateways:
        payment_methods.append({
            'name': gateway.gateway_name,
            'currencies': gateway.currencies_supported.split(',') if gateway.currencies_supported else [],
            'fee_percentage': float(gateway.fee_percentage),
            'fee_fixed': float(gateway.fee_fixed),
            'available': True
        })
    
    # Ajouter le cash pour Haïti
    if user_country == 'HT':
        payment_methods.append({
            'name': 'cash',
            'currencies': ['HTG'],
            'fee_percentage': 0,
            'fee_fixed': 0,
            'available': True,
            'collection_points': True
        })
    
    return jsonify({
        'country': user_country,
        'payment_methods': payment_methods
    }), 200


@contribution_bp.route('/estimate-fees', methods=['POST'])
def estimate_fees():
    """Estime les frais pour une contribution"""
    data = request.get_json(silent=True) or {}
    try:
        amount = Decimal(str(data['amount']))
        if not amount.is_finite() or amount <= 0:
            raise InvalidOperation
        currency = data['currency']
        payment_method = data['payment_method']
    except (KeyError, InvalidOperation):
        return jsonify({'error': 'amount (> 0), currency et payment_method requis'}), 400
    country = data.get('country', 'HT')
    
    from app.utils.exchange_rates import get_exchange_rate
    
    # Frais de change
    exchange_rate = get_exchange_rate(currency, 'HTG')
    conversion_fee = amount * Decimal('0.01')  # 1% de frais de change
    
    # Frais de paiement
    gateway = PaymentGatewayConfig.query.filter_by(
        country_code=country,
        gateway_name=payment_method,
        is_active=True
    ).first()
    
    gateway_fee = amount * (gateway.fee_percentage / 100) + gateway.fee_fixed if gateway else Decimal('0')
    
    # Commission plateforme
    platform_fee = amount * Decimal('0.03')  # 3% par défaut
    
    total_fees = gateway_fee + conversion_fee + platform_fee
    net_amount = amount - total_fees
    
    return jsonify({
        'amount': float(amount),
        'currency': currency,
        'exchange_rate': float(exchange_rate),
        'amount_htg': float(amount * exchange_rate),
        'fees': {
            'gateway_fee': float(gateway_fee),
            'conversion_fee': float(conversion_fee),
            'platform_fee': float(platform_fee),
            'total': float(total_fees)
        },
        'net_amount': float(net_amount),
        'net_amount_htg': float(net_amount * exchange_rate)
    }), 200