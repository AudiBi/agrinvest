"""
Routes pour les webhooks (intégrations externes)
"""

from flask import request, jsonify, current_app, Blueprint
from app.api import api_bp
from app.models import Contribution, Project, User, FundTransfer
from app.extensions import db
import hmac
import hashlib


webhook_bp = Blueprint('webhooks', __name__, url_prefix='/webhooks')


@webhook_bp.route('/wise', methods=['POST'])
def wise_webhook():
    """Webhook pour les transferts Wise"""
    signature = request.headers.get('X-Wise-Signature')
    payload = request.get_data(as_text=True)
    
    # Vérifier la signature
    expected = hmac.new(
        current_app.config['WISE_API_KEY'].encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected):
        return jsonify({'error': 'Invalid signature'}), 401
    
    data = request.get_json()
    
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
    data = request.get_json()
    
    payment_id = data.get('payment_id')
    transaction_id = data.get('transaction_id')
    status = data.get('status')
    
    contribution = Contribution.query.filter_by(moncash_payment_id=payment_id).first()
    
    if contribution:
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
    except (ValueError, stripe.error.SignatureVerificationError):
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