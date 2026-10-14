# app/utils/stripe.py
"""
Intégration Stripe pour AgriInvest Haïti
"""

import stripe
from flask import current_app, jsonify
from decimal import Decimal


def get_stripe_client():
    """Retourne le client Stripe configuré"""
    stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
    return stripe


def create_stripe_payment_intent(contribution):
    """
    Crée un PaymentIntent Stripe
    
    Args:
        contribution: Objet Contribution
    
    Returns:
        PaymentIntent Stripe
    """
    try:
        stripe_client = get_stripe_client()
        
        intent = stripe_client.PaymentIntent.create(
            amount=int(contribution.amount * 100),  # Stripe utilise les centimes
            currency=contribution.currency.lower(),
            metadata={
                'contribution_id': contribution.id,
                'project_id': contribution.project_id,
                'investor_id': contribution.investor_id,
                'contribution_type': 'investment'
            },
            receipt_email=contribution.investor.email,
            description=f"Investissement dans le projet {contribution.project.title}"
        )
        
        return {
            'client_secret': intent.client_secret,
            'payment_intent_id': intent.id,
            'amount': intent.amount / 100,
            'currency': intent.currency,
            'status': intent.status
        }
    
    except stripe.StripeError as e:
        current_app.logger.error(f"Stripe error: {e}")
        return None


def handle_stripe_webhook(payload, sig_header):
    """
    Gère les webhooks Stripe
    
    Args:
        payload: Corps de la requête
        sig_header: En-tête de signature
    
    Returns:
        Événement Stripe traité
    """
    try:
        stripe_client = get_stripe_client()
        webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')
        
        event = stripe_client.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
        
        # Traiter selon le type d'événement
        if event['type'] == 'payment_intent.succeeded':
            _handle_payment_success(event['data']['object'])
        elif event['type'] == 'payment_intent.payment_failed':
            _handle_payment_failure(event['data']['object'])
        elif event['type'] == 'charge.refunded':
            _handle_refund(event['data']['object'])
        
        return event
    
    except stripe.SignatureVerificationError as e:
        current_app.logger.error(f"Stripe webhook signature error: {e}")
        return None


def refund_stripe_payment(payment_intent_id, amount=None):
    """
    Rembourse un paiement Stripe
    
    Args:
        payment_intent_id: ID du PaymentIntent
        amount: Montant à rembourser (optionnel)
    
    Returns:
        bool: Succès ou échec
    """
    try:
        stripe_client = get_stripe_client()
        
        refund_params = {'payment_intent': payment_intent_id}
        if amount:
            refund_params['amount'] = int(amount * 100)
        
        refund = stripe_client.Refund.create(**refund_params)
        return refund.status == 'succeeded'
    
    except stripe.StripeError as e:
        current_app.logger.error(f"Stripe refund error: {e}")
        return False


def retrieve_stripe_payment_intent(payment_intent_id):
    """
    Récupère un PaymentIntent Stripe
    
    Args:
        payment_intent_id: ID du PaymentIntent
    
    Returns:
        PaymentIntent ou None
    """
    try:
        stripe_client = get_stripe_client()
        return stripe_client.PaymentIntent.retrieve(payment_intent_id)
    except stripe.StripeError as e:
        current_app.logger.error(f"Stripe retrieve error: {e}")
        return None


def _handle_payment_success(payment_intent):
    """Gère un paiement réussi"""
    from app.models import Contribution
    from app.extensions import db
    
    contribution_id = payment_intent.get('metadata', {}).get('contribution_id')
    if contribution_id:
        contribution = Contribution.query.get(int(contribution_id))
        if contribution and contribution.status == 'pending':
            contribution.mark_completed()
            db.session.commit()


def _handle_payment_failure(payment_intent):
    """Gère un paiement échoué"""
    from app.models import Contribution
    from app.extensions import db
    
    contribution_id = payment_intent.get('metadata', {}).get('contribution_id')
    if contribution_id:
        contribution = Contribution.query.get(int(contribution_id))
        if contribution and contribution.status == 'pending':
            contribution.mark_failed()
            db.session.commit()


def _handle_refund(charge):
    """Gère un remboursement"""
    from app.models import Contribution
    from app.extensions import db
    
    payment_intent_id = charge.get('payment_intent')
    if payment_intent_id:
        contribution = Contribution.query.filter_by(
            stripe_payment_intent_id=payment_intent_id
        ).first()
        if contribution:
            contribution.mark_refunded()
            db.session.commit()