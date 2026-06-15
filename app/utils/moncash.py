# app/utils/moncash.py
"""
Intégration MonCash pour AgriInvest Haïti (paiements locaux)
"""

import requests
import base64
import hashlib
import hmac
from flask import current_app
from decimal import Decimal


def get_moncash_api_url():
    """Retourne l'URL de l'API MonCash"""
    environment = current_app.config.get('MONCASH_ENVIRONMENT', 'sandbox')
    if environment == 'production':
        return "https://api.moncashapi.com/v1"
    return "https://sandbox.moncashapi.com/v1"


def get_moncash_access_token():
    """Récupère le token d'accès MonCash"""
    client_id = current_app.config.get('MONCASH_CLIENT_ID')
    client_secret = current_app.config.get('MONCASH_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        return None
    
    auth_string = f"{client_id}:{client_secret}"
    encoded_auth = base64.b64encode(auth_string.encode()).decode()
    
    api_url = get_moncash_api_url()
    headers = {
        'Authorization': f'Basic {encoded_auth}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    data = {'grant_type': 'client_credentials'}
    
    try:
        response = requests.post(
            f"{api_url}/oauth/token",
            headers=headers,
            data=data
        )
        response.raise_for_status()
        return response.json().get('access_token')
    except requests.RequestException as e:
        current_app.logger.error(f"MonCash auth error: {e}")
        return None


def create_moncash_payment(contribution, return_url):
    """
    Crée un paiement MonCash
    
    Args:
        contribution: Objet Contribution
        return_url: URL de retour après paiement
    
    Returns:
        Dict avec les informations du paiement
    """
    token = get_moncash_access_token()
    if not token:
        return None
    
    api_url = get_moncash_api_url()
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    # Générer un ID de commande unique
    order_id = f"CONTRIB_{contribution.id}_{int(datetime.now().timestamp())}"
    
    data = {
        'amount': str(float(contribution.amount_htg)),
        'orderId': order_id,
        'returnUrl': return_url,
        'metadata': {
            'contribution_id': contribution.id,
            'project_id': contribution.project_id,
            'investor_id': contribution.investor_id
        }
    }
    
    try:
        response = requests.post(
            f"{api_url}/payment/create",
            headers=headers,
            json=data
        )
        response.raise_for_status()
        
        result = response.json()
        return {
            'payment_id': result.get('paymentId'),
            'order_id': order_id,
            'payment_url': result.get('paymentUrl'),
            'status': result.get('status')
        }
    
    except requests.RequestException as e:
        current_app.logger.error(f"MonCash create payment error: {e}")
        return None


def handle_moncash_webhook(request_body):
    """
    Gère les webhooks MonCash
    
    Args:
        request_body: Corps de la requête
    
    Returns:
        Événement traité
    """
    import json
    data = json.loads(request_body)
    
    payment_id = data.get('paymentId')
    transaction_id = data.get('transactionId')
    status = data.get('status')
    
    if status == 'completed':
        _handle_payment_completed(payment_id, transaction_id)
    elif status == 'failed':
        _handle_payment_failed(payment_id)
    
    return data


def refund_moncash_payment(payment_id):
    """
    Rembourse un paiement MonCash
    
    Args:
        payment_id: ID du paiement MonCash
    
    Returns:
        bool: Succès ou échec
    """
    token = get_moncash_access_token()
    if not token:
        return False
    
    api_url = get_moncash_api_url()
    headers = {'Authorization': f'Bearer {token}'}
    
    try:
        response = requests.post(
            f"{api_url}/payment/{payment_id}/refund",
            headers=headers
        )
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        current_app.logger.error(f"MonCash refund error: {e}")
        return False


def retrieve_moncash_payment(payment_id):
    """
    Récupère les détails d'un paiement MonCash
    
    Args:
        payment_id: ID du paiement MonCash
    
    Returns:
        Détails du paiement
    """
    token = get_moncash_access_token()
    if not token:
        return None
    
    api_url = get_moncash_api_url()
    headers = {'Authorization': f'Bearer {token}'}
    
    try:
        response = requests.get(
            f"{api_url}/payment/{payment_id}",
            headers=headers
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        current_app.logger.error(f"MonCash retrieve error: {e}")
        return None


def _handle_payment_completed(payment_id, transaction_id):
    """Gère un paiement complété"""
    from app.models import Contribution
    from app.extensions import db
    
    # Récupérer la contribution via le payment_id stocké
    contribution = Contribution.query.filter_by(
        moncash_payment_id=payment_id
    ).first()
    
    if contribution and contribution.status == 'pending':
        contribution.moncash_transaction_id = transaction_id
        contribution.mark_completed()
        db.session.commit()


def _handle_payment_failed(payment_id):
    """Gère un paiement échoué"""
    from app.models import Contribution
    from app.extensions import db
    
    contribution = Contribution.query.filter_by(
        moncash_payment_id=payment_id
    ).first()
    
    if contribution and contribution.status == 'pending':
        contribution.mark_failed()
        db.session.commit()