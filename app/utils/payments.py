# app/utils/payments.py
"""Façade des passerelles de paiement (Stripe, PayPal, MonCash) pour les routes de contribution.

Les fonctions process_* retournent un dict (avec 'id' et 'approval_url' quand applicable) ou
lèvent RuntimeError ; verify_payment et process_refund échouent « fermé » (False).
"""

from flask import current_app

from app.utils import stripe as stripe_gateway
from app.utils import paypal as paypal_gateway
from app.utils import moncash as moncash_gateway


def _return_urls():
    base = current_app.config.get('BASE_URL', 'http://localhost:5000').rstrip('/')
    return f'{base}/payment/success', f'{base}/payment/cancel'


def process_stripe_payment(contribution):
    intent = stripe_gateway.create_stripe_payment_intent(contribution)
    if not intent:
        raise RuntimeError('Échec de création du paiement Stripe')
    return {**intent, 'id': intent['payment_intent_id']}


def process_paypal_payment(contribution):
    return_url, cancel_url = _return_urls()
    order = paypal_gateway.create_paypal_payment(contribution, return_url, cancel_url)
    if not order:
        raise RuntimeError('Échec de création du paiement PayPal')
    return {**order, 'id': order['order_id']}


def process_moncash_payment(contribution):
    return_url, _ = _return_urls()
    payment = moncash_gateway.create_moncash_payment(contribution, return_url)
    if not payment:
        raise RuntimeError('Échec de création du paiement MonCash')
    return {**payment, 'approval_url': payment.get('payment_url')}


def _gateway_id(contribution):
    """(méthode, identifiant stocké côté serveur) ; jamais l'identifiant fourni par le client."""
    method = contribution.payment_method
    if method == 'stripe':
        return method, contribution.stripe_payment_intent_id
    if method == 'paypal':
        return method, contribution.paypal_order_id
    if method == 'moncash':
        return method, contribution.moncash_payment_id
    return method, None


def verify_payment(contribution, client_payment_id=None):
    """Vrai seulement si la passerelle confirme le paiement enregistré pour cette contribution."""
    method, gateway_id = _gateway_id(contribution)
    if not gateway_id or (client_payment_id and client_payment_id != gateway_id):
        return False

    if method == 'stripe':
        intent = stripe_gateway.retrieve_stripe_payment_intent(gateway_id)
        return bool(
            intent
            and intent.status == 'succeeded'
            and str(intent.metadata.get('contribution_id')) == str(contribution.id)
        )
    if method == 'paypal':
        order = paypal_gateway.retrieve_paypal_payment(gateway_id)
        return bool(order and order.get('status') == 'COMPLETED')
    if method == 'moncash':
        payment = moncash_gateway.retrieve_moncash_payment(gateway_id)
        return bool(payment and str(payment.get('status', '')).lower() == 'completed')
    return False


def process_refund(contribution):
    """Rembourse via la passerelle d'origine. Lève ValueError si la méthode n'est pas remboursable."""
    method, gateway_id = _gateway_id(contribution)
    if not gateway_id:
        raise ValueError(f'Remboursement automatique impossible pour la méthode {method}')

    if method == 'stripe':
        return stripe_gateway.refund_stripe_payment(gateway_id)
    if method == 'paypal':
        order = paypal_gateway.retrieve_paypal_payment(gateway_id)
        try:
            capture_id = order['purchase_units'][0]['payments']['captures'][0]['id']
        except (TypeError, KeyError, IndexError):
            return False
        return paypal_gateway.refund_paypal_payment(capture_id)
    if method == 'moncash':
        return moncash_gateway.refund_moncash_payment(gateway_id)
    return False
