# app/utils/paypal.py
"""
Intégration PayPal pour AgriInvest Haïti
"""

import requests
from flask import current_app
from decimal import Decimal


def get_paypal_access_token():
    """Récupère le token d'accès PayPal"""
    client_id = current_app.config.get('PAYPAL_CLIENT_ID')
    client_secret = current_app.config.get('PAYPAL_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        return None
    
    auth = (client_id, client_secret)
    
    # Déterminer l'URL de l'API
    mode = current_app.config.get('PAYPAL_MODE', 'sandbox')
    if mode == 'live':
        url = "https://api.paypal.com/v1/oauth2/token"
    else:
        url = "https://api.sandbox.paypal.com/v1/oauth2/token"
    
    data = {'grant_type': 'client_credentials'}
    
    try:
        response = requests.post(url, auth=auth, data=data)
        response.raise_for_status()
        return response.json().get('access_token')
    except requests.RequestException as e:
        current_app.logger.error(f"PayPal auth error: {e}")
        return None


def get_paypal_api_url():
    """Retourne l'URL de base de l'API PayPal"""
    mode = current_app.config.get('PAYPAL_MODE', 'sandbox')
    if mode == 'live':
        return "https://api.paypal.com/v2"
    return "https://api.sandbox.paypal.com/v2"


def create_paypal_payment(contribution, return_url, cancel_url):
    """
    Crée un paiement PayPal
    
    Args:
        contribution: Objet Contribution
        return_url: URL de retour après succès
        cancel_url: URL d'annulation
    
    Returns:
        Dict avec les informations du paiement
    """
    token = get_paypal_access_token()
    if not token:
        return None
    
    api_url = get_paypal_api_url()
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    data = {
        'intent': 'CAPTURE',
        'purchase_units': [{
            'reference_id': f'contribution_{contribution.id}',
            'amount': {
                'currency_code': contribution.currency,
                'value': str(float(contribution.amount))
            },
            'description': f"Investissement dans le projet {contribution.project.title}",
            'custom_id': str(contribution.id)
        }],
        'application_context': {
            'return_url': return_url,
            'cancel_url': cancel_url,
            'brand_name': 'AgriInvest Haïti',
            'locale': 'fr-FR',
            'shipping_preference': 'NO_SHIPPING',
            'user_action': 'PAY_NOW'
        }
    }
    
    try:
        response = requests.post(
            f"{api_url}/checkout/orders",
            headers=headers,
            json=data
        )
        response.raise_for_status()
        
        result = response.json()
        
        # Trouver le lien d'approbation
        approval_url = None
        for link in result.get('links', []):
            if link.get('rel') == 'approve':
                approval_url = link.get('href')
                break
        
        return {
            'order_id': result.get('id'),
            'approval_url': approval_url,
            'status': result.get('status')
        }
    
    except requests.RequestException as e:
        current_app.logger.error(f"PayPal create payment error: {e}")
        return None


def handle_paypal_webhook(request_body, headers):
    """
    Gère les webhooks PayPal
    
    Args:
        request_body: Corps de la requête
        headers: En-têtes HTTP
    
    Returns:
        Événement traité
    """
    # Vérifier la signature
    if not verify_paypal_webhook_signature(request_body, headers):
        current_app.logger.warning("Invalid PayPal webhook signature")
        return None
    
    import json
    event = json.loads(request_body)
    
    event_type = event.get('event_type')
    resource = event.get('resource', {})
    
    if event_type == 'CHECKOUT.ORDER.APPROVED':
        _handle_order_approved(resource)
    elif event_type == 'PAYMENT.CAPTURE.COMPLETED':
        _handle_payment_completed(resource)
    elif event_type == 'PAYMENT.CAPTURE.REFUNDED':
        _handle_refund_completed(resource)
    
    return event


def verify_paypal_webhook_signature(request_body, headers):
    """Vérifie la signature via l'API PayPal « verify-webhook-signature ». Échoue fermé."""
    webhook_id = current_app.config.get('PAYPAL_WEBHOOK_ID')
    token = get_paypal_access_token()
    if not webhook_id or not token:
        return False

    import json
    try:
        event = json.loads(request_body)
        payload = {
            'auth_algo': headers.get('PAYPAL-AUTH-ALGO'),
            'cert_url': headers.get('PAYPAL-CERT-URL'),
            'transmission_id': headers.get('PAYPAL-TRANSMISSION-ID'),
            'transmission_sig': headers.get('PAYPAL-TRANSMISSION-SIG'),
            'transmission_time': headers.get('PAYPAL-TRANSMISSION-TIME'),
            'webhook_id': webhook_id,
            'webhook_event': event,
        }
        if not all(v for k, v in payload.items() if k != 'webhook_event'):
            return False
        base = get_paypal_api_url().rsplit('/v2', 1)[0]
        response = requests.post(
            f"{base}/v1/notifications/verify-webhook-signature",
            json=payload,
            headers={'Authorization': f'Bearer {token}'},
            timeout=10,
        )
        response.raise_for_status()
        return response.json().get('verification_status') == 'SUCCESS'
    except (requests.RequestException, ValueError) as e:
        current_app.logger.error(f"PayPal webhook verification error: {e}")
        return False


def refund_paypal_payment(capture_id, amount=None):
    """
    Rembourse un paiement PayPal
    
    Args:
        capture_id: ID de la capture
        amount: Montant à rembourser
    
    Returns:
        bool: Succès ou échec
    """
    token = get_paypal_access_token()
    if not token:
        return False
    
    api_url = get_paypal_api_url()
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    data = {}
    if amount:
        data['amount'] = {
            'currency_code': 'HTG',
            'value': str(float(amount))
        }
    
    try:
        response = requests.post(
            f"{api_url}/payments/captures/{capture_id}/refund",
            headers=headers,
            json=data
        )
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        current_app.logger.error(f"PayPal refund error: {e}")
        return False


def retrieve_paypal_payment(order_id):
    """
    Récupère un paiement PayPal
    
    Args:
        order_id: ID de la commande PayPal
    
    Returns:
        Détails du paiement
    """
    token = get_paypal_access_token()
    if not token:
        return None
    
    api_url = get_paypal_api_url()
    headers = {'Authorization': f'Bearer {token}'}
    
    try:
        response = requests.get(
            f"{api_url}/checkout/orders/{order_id}",
            headers=headers
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        current_app.logger.error(f"PayPal retrieve error: {e}")
        return None


def _handle_order_approved(resource):
    """Gère une commande approuvée"""
    pass


def _handle_payment_completed(resource):
    """Gère un paiement complété"""
    from app.models import Contribution
    from app.extensions import db
    
    custom_id = resource.get('custom_id')
    if custom_id:
        from app.utils.payments import CONFIRMABLE_STATUSES, payment_matches
        contribution = db.session.get(Contribution, int(custom_id))
        amount = resource.get('amount') or {}
        if (contribution and contribution.status in CONFIRMABLE_STATUSES
                and payment_matches(contribution, amount.get('value'), amount.get('currency_code'))):
            contribution.mark_completed()
        elif contribution and contribution.status == 'pending':
            current_app.logger.error(f"PayPal: montant/devise inattendus pour la contribution {contribution.id}")


def _handle_refund_completed(resource):
    """Gère un remboursement complété"""
    from app.models import Contribution
    from app.extensions import db
    
    custom_id = resource.get('custom_id')
    if custom_id:
        contribution = Contribution.query.get(int(custom_id))
        if contribution:
            contribution.mark_refunded()
            db.session.commit()