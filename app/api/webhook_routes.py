"""
Routes pour les webhooks (intégrations externes)
"""

from flask import request, jsonify, current_app, Blueprint
from app.api import api_bp
from app.models import Contribution, Project, User, FundTransfer
from app.models.contribution import ContributionStatus, utc_now
from app.extensions import db
import hmac
import hashlib
import stripe


webhook_bp = Blueprint('webhooks', __name__, url_prefix='/webhooks')


def _valid_hmac(body, signature, secret):
    """Vérifie une signature HMAC-SHA256 hex. Refuse tout si secret ou signature absents."""
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature.strip().lower(), expected)


@webhook_bp.route('/wise', methods=['POST'])
def wise_webhook():
    """Webhook pour les transferts Wise"""
    if not _valid_hmac(request.get_data(), request.headers.get('X-Wise-Signature'),
                       current_app.config.get('WISE_WEBHOOK_SECRET')):
        return jsonify({'error': 'Invalid signature'}), 401
    
    data = request.get_json(silent=True) or {}
    
    # Traiter l'événement
    if data.get('event_type') == 'transfer.state_changed':
        transfer_reference = data.get('transfer', {}).get('reference')
        new_state = data.get('transfer', {}).get('state')
        
        transfer = FundTransfer.query.filter_by(transfer_reference=transfer_reference).first()
        
        if transfer:
            if new_state == 'completed':
                transfer.status = 'completed'
                transfer.completed_at = utc_now()
            elif new_state == 'failed':
                transfer.status = 'failed'
            
            db.session.commit()
    
    return jsonify({'status': 'ok'}), 200


@webhook_bp.route('/moncash', methods=['POST'])
def moncash_webhook():
    """Webhook pour les paiements MonCash"""
    # Signature HMAC-SHA256 du corps brut (secret requis : fail closed)
    if not _valid_hmac(request.get_data(), request.headers.get('X-MonCash-Signature'),
                       current_app.config.get('MONCASH_WEBHOOK_SECRET')):
        return jsonify({'error': 'Invalid signature'}), 401
    
    data = request.get_json(silent=True) or {}
    
    payment_id = data.get('payment_id')
    transaction_id = data.get('transaction_id')
    status = data.get('status')
    
    contribution = Contribution.query.filter_by(moncash_payment_id=payment_id).first() if payment_id else None
    
    # Idempotence : un paiement déjà finalisé n'est jamais retraité
    if contribution and contribution.status != ContributionStatus.COMPLETED:
        if status == 'completed':
            contribution.mark_completed()
            contribution.moncash_transaction_id = transaction_id
        elif status == 'failed':
            contribution.mark_failed()
        
        db.session.commit()
    
    return jsonify({'status': 'ok'}), 200


@webhook_bp.route('/stripe/connect', methods=['POST'])
def stripe_connect_webhook():
    """Webhook pour Stripe Connect (transferts vers Haïti)"""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, current_app.config['STRIPE_CONNECT_WEBHOOK_SECRET']
        )
    except (ValueError, stripe.SignatureVerificationError):
        return jsonify({'error': 'Invalid signature'}), 401
    
    if event['type'] == 'transfer.paid':
        transfer_data = event['data']['object']
        # Traiter le transfert
        # ...
    
    return jsonify({'status': 'ok'}), 200


@webhook_bp.route('/twilio', methods=['POST'])
def twilio_webhook():
    """Webhook pour les SMS Twilio"""
    data = request.form
    
    message_sid = data.get('MessageSid')
    message_status = data.get('MessageStatus')
    to = data.get('To')
    
    # Mettre à jour le statut du message dans la base de données
    # ...
    
    return jsonify({'status': 'ok'}), 200