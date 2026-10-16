"""
Routes pour les paiements
"""

from flask import request, jsonify, current_app, Blueprint
from flask_login import login_required, current_user
from app.api import api_bp
from app.models import PaymentGatewayConfig, Contribution, Project
from app.extensions import db
import stripe
from decimal import Decimal
from app.utils.payments import CONFIRMABLE_STATUSES, payment_matches


payment_bp = Blueprint('payments', __name__, url_prefix='/payments')


@payment_bp.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    """Webhook Stripe pour les événements de paiement"""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, current_app.config['STRIPE_WEBHOOK_SECRET']
        )
    except ValueError:
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.SignatureVerificationError:
        return jsonify({'error': 'Invalid signature'}), 400
    
    # Traiter l'événement
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        # Mettre à jour la contribution correspondante
        contribution = Contribution.query.filter_by(
            stripe_payment_intent_id=payment_intent['id']
        ).first()
        
        if contribution and contribution.status in CONFIRMABLE_STATUSES:
            paid = Decimal(payment_intent.get('amount_received', payment_intent['amount'])) / 100
            if not payment_matches(contribution, paid, payment_intent.get('currency')):
                current_app.logger.error(
                    f"Stripe: montant/devise inattendus pour la contribution {contribution.id} "
                    f"({paid} {payment_intent.get('currency')}), confirmation refusée")
                return jsonify({'status': 'amount_mismatch'}), 200
            contribution.mark_completed()
    
    elif event['type'] == 'payment_intent.payment_failed':
        payment_intent = event['data']['object']
        contribution = Contribution.query.filter_by(
            stripe_payment_intent_id=payment_intent['id']
        ).first()
        
        if contribution and contribution.status == 'pending':
            contribution.mark_failed()
    
    return jsonify({'status': 'success'}), 200


@payment_bp.route('/webhook/paypal', methods=['POST'])
def paypal_webhook():
    """Webhook PayPal (signature vérifiée via l'API PayPal, échec fermé)"""
    from app.utils.paypal import handle_paypal_webhook
    
    event = handle_paypal_webhook(request.get_data(as_text=True), request.headers)
    if event is None:
        return jsonify({'error': 'Invalid signature'}), 401
    return jsonify({'status': 'success'}), 200


# MonCash : même gestionnaire (signature HMAC + idempotence) que /webhooks/moncash
from app.api.webhook_routes import moncash_webhook  # noqa: E402

payment_bp.add_url_rule('/webhook/moncash', 'moncash_webhook', moncash_webhook, methods=['POST'])


@payment_bp.route('/config', methods=['GET'])
def get_payment_config():
    """Récupère la configuration de paiement pour le frontend"""
    country = request.args.get('country', 'HT')
    
    gateways = PaymentGatewayConfig.query.filter_by(
        country_code=country,
        is_active=True
    ).all()
    
    config = {
        'stripe': {
            'publishable_key': current_app.config['STRIPE_PUBLIC_KEY'],
            'available': any(g.gateway_name == 'stripe' for g in gateways)
        },
        'paypal': {
            'client_id': current_app.config['PAYPAL_CLIENT_ID'],
            'available': any(g.gateway_name == 'paypal' for g in gateways)
        },
        'moncash': {
            'environment': current_app.config['MONCASH_ENVIRONMENT'],
            'available': any(g.gateway_name == 'moncash' for g in gateways)
        }
    }
    
    return jsonify(config), 200


@payment_bp.route('/create-payment-intent', methods=['POST'])
@login_required
def create_payment_intent():
    """Crée un payment intent Stripe"""
    data = request.get_json()
    amount = data.get('amount')
    currency = data.get('currency', 'usd')
    contribution_id = data.get('contribution_id')
    
    contribution = Contribution.query.get_or_404(contribution_id)
    
    if contribution.investor_id != current_user.id:
        return jsonify({'error': 'Non autorisé'}), 403
    
    try:
        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),  # Stripe utilise les centimes
            currency=currency,
            metadata={
                'contribution_id': contribution_id,
                'user_id': current_user.id,
                'project_id': contribution.project_id
            }
        )
        
        contribution.stripe_payment_intent_id = intent.id
        db.session.commit()
        
        return jsonify({
            'client_secret': intent.client_secret,
            'payment_intent_id': intent.id
        }), 200
        
    except stripe.StripeError as e:
        return jsonify({'error': str(e)}), 400